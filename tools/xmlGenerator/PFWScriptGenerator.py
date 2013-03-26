#!/usr/bin/python3
# -*-coding:utf-8 -*

# INTEL CONFIDENTIAL
# Copyright  2013 Intel
# Corporation All Rights Reserved.
#
# The source code contained or described herein and all documents related to
# the source code ("Material") are owned by Intel Corporation or its suppliers
# or licensors. Title to the Material remains with Intel Corporation or its
# suppliers and licensors. The Material contains trade secrets and proprietary
# and confidential information of Intel or its suppliers and licensors. The
# Material is protected by worldwide copyright and trade secret laws and
# treaty provisions. No part of the Material may be used, copied, reproduced,
# modified, published, uploaded, posted, transmitted, distributed, or
# disclosed in any way without Intels prior express written permission.
#
# No license under any patent, copyright, trade secret or other intellectual
# property right is granted to or conferred upon you by disclosure or delivery
# of the Materials, either expressly, by implication, inducement, estoppel or
# otherwise. Any license under such intellectual property rights must be
# express and approved by Intel in writing.


import re
import sys
import copy
import imp

try:
    import argparse
except ImportError:
    import optparse

# =====================================================================
""" Context classes, used during propagation and the "to PFW script" step """
# =====================================================================

class PropagationContextItem(list) :
    """Handle an item during the propagation step"""
    def __copy__(self):
        """C.__copy__() -> a shallow copy of C"""
        return self.__class__(self)

class PropagationContextElement(PropagationContextItem) :
    """Handle an Element during the propagation step"""
    def getElementsFromName(self, name):
        matchingElements = []
        for element in self :
            if element.getName() == name :
                matchingElements.append(element)
        return matchingElements


class PropagationContextOption(PropagationContextItem) :
    """Handle an Option during the propagation step"""
    def getOptionItems (self, itemName):
        items = []
        for options in self :
            items.append(options.getOption(itemName))
        return items


class PropagationContext() :
    """Handle the context during the propagation step"""
    def __init__(self, propagationContext=None) :

        if propagationContext == None :
            self._context = {
                "DomainOptions" : PropagationContextOption() ,
                "Configurations" : PropagationContextElement() ,
                "ConfigurationOptions" : PropagationContextOption() ,
                "Rules" : PropagationContextElement() ,
                "PathOptions" : PropagationContextOption() ,
        }
        else :
            self._context = propagationContext

    def copy(self):
        """return a copy of the context"""
        contextCopy = self._context.copy()

        for key in iter(self._context) :
            contextCopy[key] = contextCopy[key].__copy__()

        return self.__class__(contextCopy)

    def getDomainOptions (self):
        return self._context["DomainOptions"]

    def getConfigurations (self):
        return self._context["Configurations"]

    def getConfigurationOptions (self):
        return self._context["ConfigurationOptions"]

    def getRules (self):
        return self._context["Rules"]

    def getPathOptions (self):
        return self._context["PathOptions"]

# ---------------------------------------------------------------------------

class PFWScriptContext ():
    """handle the context during the PFW script generation"""

    def __init__(self, prefixIncrease="    ") :
        self._context = {
            "Prefix" : "" ,
            "DomainName" : "" ,
            "ConfigurationName" : "" ,
            "SequenceAwareness" : False ,
        }
        self._prefixIncrease = prefixIncrease

    def increasePrefix(self) :
        self._context["Prefix"] = self._prefixIncrease + self._context["Prefix"]

    def getNewLinePrefix(self) :
        """return a prefix with decorative new line

        return r"\"+"\n"+" "*increased prefix length"""
        return "\\\n" + self._prefixIncrease + " "* len(self.getPrefix())

    def copy(self) :
        copy = PFWScriptContext ()
        copy._context = self._context.copy()
        return copy

    def setDomainName (self, name) :
        self._context["DomainName"] = name

    def setConfigurationName (self, name) :
        self._context["ConfigurationName"] = name

    def setSequenceAwareness (self, sequenceAwareness) :
        self._context["SequenceAwareness"] = sequenceAwareness

    def getPrefix(self):
        return self._context["Prefix"]

    def getDomainName (self):
        return self._context["DomainName"]

    def getConfigurationName(self):
        return self._context["ConfigurationName"]

    def getSequenceAwareness(self):
        return self._context["SequenceAwareness"]

# =====================================================
"""Element option container"""
# =====================================================

class Options () :
    """handle element options"""
    def __init__(self, options=[], optionNames=[]) :
        self.options = dict(zip(optionNames, options))
        # print(options,optionNames,self.options)


    def __str__(self) :
        ops2str = []
        for name, argument in self.options.items() :
            ops2str.append(str(name) + "=\"" + str(argument) + "\"")

        return " ".join(ops2str)

    def getOption(self, name):
        """get option by its name, if it does not exist return empty string"""
        return self.options.get(name, "")

    def setOption(self, name, newOption):
        """set option by its name"""
        self.options[name] = newOption

    def copy (self):
        """D.copy() -> a shallow copy of D"""
        copy = Options()
        copy.options = self.options.copy()
        return copy

# ====================================================
"""Definition of all element class"""
# ====================================================

class Element:
    """ implement a basic element

    It is the class base for all other elements as Domain, Configuration..."""
    tag = "unknown"
    optionNames = ["Name"]
    childWhiteList = []
    optionDelimiter = " "

    def __init__(self, line=None) :

        if line == None :
            self.option = Options([], self.optionNames)
        else :
            self.option = self.optionFromLine(line)

        self.children = []

    def optionFromLine(self, line) :
        # get ride of spaces
        line = line.strip()

        options = self.extractOptions(line)

        return Options(options, self.optionNames)

    def extractOptions(self, line) :
        """return the line splited by the optionDelimiter atribute

        Option list length is less or equal to the optionNames list length
        """
        options = line.split(self.optionDelimiter, len(self.optionNames) - 1)

        # get ride of leftover spaces
        optionsStrip = list(map(str.strip, options))

        return optionsStrip

    def addChild(self, child, append=True) :
        """ A.addChid(B) -> add B to A child list if B class name is in A white List"""
        try:
            # Will raise an exception if this child is not in the white list
            self.childWhiteList.index(child.__class__.__name__)
            # If no exception was raised, add child to child list

            if append :
                self.children.append(child)
            else :
                self.children.insert(0, child)

        except ValueError:
            # the child class is not in the white list
            raise ChildNotPermitedError("", self, child)

    def addChildren(self, children, append=True) :
        """Add a list of child"""
        if append:
            # Add children at the end of the child list
            self.children.extend(children)
        else:
            # Add children at the begining of the child list
            self.children = children + self.children

    def childrenToXML(self, prefix=""):
        """return XML printed children"""
        body = ""
        for child in  self.children :
            body = body + child.toXML(prefix)

        return body

    def childrenToString(self, prefix=""):
        """return raw printed children """
        body = ""
        for child in self.children :
            body = body + child.__str__(prefix)

        return body

    def __str__(self, prefix="") :
        """return raw printed element"""
        selfToString = prefix + " " + self.tag + " " + str(self.option)
        return selfToString + "\n" + self.childrenToString(prefix + "\t")

    def toXML(self, prefix="") :
        """return XML printed element"""
        # full = begin:"<tag options" + body:children.toXML + end:"</tag>"
        begin = prefix + "<" + self.tag + " " + str(self.option)
        body = self.childrenToXML(prefix + "\t")

        if body == "" :
            full = begin + "/>"
        else :
            end = prefix + "</" + self.tag + ">"
            full = begin + ">\n" + body + end

        return full + "\n"

    def extractChildrenByClass(self, classTypeList) :
        """return all children whose class is in the list argument

        return a list of all children whose class in the list "classTypeList" (second arguments)"""
        selectedChildren = []

        for child in  self.children :
            for classtype in classTypeList :
                if child.__class__ == classtype :
                    selectedChildren.append(child)
                    break
        return selectedChildren

    def propagate (self, context=PropagationContext()):
        """call the propagate method of all children"""
        for child in  self.children :
            child.propagate(context)

    def getName(self):
        """return name option value. If none return "" """
        return self.option.getOption("Name")

    def setName(self, name):
        self.option.setOption("Name", name)

    def toPFWScript (self, context=PFWScriptContext()) :
        script = ""
        for child in  self.children :
            script += child.toPFWScript(context)
        return script


# ----------------------------------------------------------

class ElementWithTag (Element):
    """Element of this class are declared with a tag  => line == "tag: .*" """
    def extractOptions(self, line) :
        lineWithoutTag = line.split(":", 1)[-1].strip()
        options = super().extractOptions(lineWithoutTag)
        return options

# ----------------------------------------------------------

class ElementWithInheritance(Element):
    def propagate (self, context=PropagationContext) :
        """propagate some proprieties to children"""

        # copy the context so that everything that hapend next will only affect
        # children
        contextCopy = context.copy()

        # check for inheritance
        self.Inheritance(contextCopy)

        # call the propagate method of all children
        super().propagate(contextCopy)


class ElementWithRuleInheritance(ElementWithInheritance):
    """class that will give to its children its rules"""
    def ruleInheritance(self, context):
        """Add its rules to the context and get context rules"""

        # extract all children rule and operator
        childRules = self.extractChildrenByClass([Operator, Rule])

        # get context rules
        contextRules = context.getRules()

        # adopt rules of the beginning of the context
        self.addChildren(contextRules, append=False)

        # add previously extract rules to the context
        contextRules += childRules


# ----------------------------------------------------------

class EmptyLine (Element) :
    """This class represents an empty line.

    Will raise "EmptyLineWarning" exception at instanciation."""

    tag = "emptyLine"
    match = re.compile(r"[ \t]*\n?$").match
    def __init__ (self, line):
       raise EmptyLineWarning(line)

# ----------------------------------------------------------

class Commentary(Element):
    """This class represents a commentary.

    Will raise "CommentWarning" exception at instanciation."""

    tag = "commentary"
    optionNames = ["comment"]
    match = re.compile(r"#").match
    def __init__ (self, line):
       raise CommentWarning(line)

# ----------------------------------------------------------

class Path (ElementWithInheritance) :
    """class implementing the "path = value" concept"""
    tag = "path"
    optionNames = ["Name", "value"]
    match = re.compile(r".+=").match
    optionDelimiter = "="
    PFWCommandParameter = "setParameter"

    def toPFWScript (self, context=PFWScriptContext()) :

        return context.getPrefix() + \
                self.PFWCommandParameter + " " + \
                self.getName() + " " + \
                self.option.getOption("value") + "\n"

    def Inheritance (self, context) :
        """check for path name inheritance"""
        self.OptionsInheritance(context)

    def OptionsInheritance (self, context) :
        """make configuration name inheritance """

        context.getPathOptions().append(self.option.copy())
        self.setName("/".join(context.getPathOptions().getOptionItems("Name")))


class GroupPath (Path, ElementWithTag) :
    tag = "component"
    match = re.compile(tag + r" *:").match
    optionNames = ["Name"]
    childWhiteList = ["Path", "GroupPath"]

    def toPFWScript (self, pfwScriptContext) :
        script = ""

        configurationChildren = self.extractChildrenByClass([GroupPath, Path])

        for configurationChild in configurationChildren :
            # add configuration settings
            script += configurationChild.toPFWScript(pfwScriptContext)

        return script

    def getPathNames (self) :
        """Return the list of all path child name"""

        pathNames = []

        paths = self.extractChildrenByClass([Path])
        for path in paths :
            pathNames.append(path.getName())

        groupPaths = self.extractChildrenByClass([GroupPath])
        for groupPath in groupPaths :
            pathNames += groupPath.getPathNames()

        return pathNames

# ----------------------------------------------------------

class Rule (Element) :
    """class implementing the rule concept

    A rule is composed of a criterion, a rule type and an criterion state.
    It should not have any child and is propagated to all configuration in parent descendants.
    """

    tag = "rule"
    optionNames = ["criterion", "type", "element"]
    match = re.compile(r"[a-zA-Z0-9_.]+ +(Is|IsNot|Includes|Excludes) +[a-zA-Z0-9_.]+").match
    childWhiteList = []

    def PFWSyntax (self, prefix=""):

        script = prefix + \
                    self.option.getOption("criterion") + " " + \
                    self.option.getOption("type") + " " + \
                    self.option.getOption("element")

        return script


class Operator (Rule) :
    """class implementing the operator concept

    An operator contains rules and other operators
    It is as rules propagated to all configuration children in parent descendants.
    It should only have the name ANY or ALL to be understood by PFW.
    """

    tag = "operator"
    optionNames = ["Name"]
    match = re.compile(r"ANY|ALL").match
    childWhiteList = ["Rule", "Operator"]

    PFWCommandRule = "setRule"
    syntax = { "ANY" : "Any" , "ALL" : "All"}

    def toPFWScript (self, context) :
        """ return a pfw commands generated from him and its child options"""
        script = ""

        # add the command name (setRule)
        script += context.getPrefix() + \
                    self.PFWCommandRule + " " + \
                    context.getDomainName() + " " + \
                    context.getConfigurationName() + " "

        # add the rule
        script += self.PFWSyntax (context.getNewLinePrefix())

        script += "\n"

        return script

    def PFWSyntax (self, prefix=""):
        """ return a pfw rule (ex : "Any{criterion1 is state1}") generated from "self" and its children options"""
        script = ""

        script += prefix + \
                    self.syntax[self.getName()] + "{ "

        rules = self.extractChildrenByClass([Rule, Operator])

        PFWRules = []
        for rule in rules :
            PFWRules.append(rule.PFWSyntax(prefix + "    "))

        script += (" , ").join(PFWRules)

        script += prefix + " }"

        return script

# ----------------------------------------------------------

class Configuration (ElementWithRuleInheritance, ElementWithTag) :
    tag = "configuration"
    optionNames = ["Name"]
    match = re.compile(r"conf *:").match
    childWhiteList = ["Rule", "Operator", "Path", "GroupPath"]

    PFWCommandConfiguration = "createConfiguration"
    PFWCommandElementSequence = "setElementSequence"
    PFWCommandSequenceAware = "setSequenceAwareness"

    PFWCommandRestoreConfiguration = "restoreConfiguration"
    PFWCommandSaveConfiguration = "saveConfiguration"

    def composition (self, context):
        """make all needed composition

        Composition is the fact that group configuration with the same name defined
        in a parent will give their rule children to this configuration
        """

        name = self.getName()
        sameNameConf = context.getConfigurations().getElementsFromName(name)

        sameNameConf.reverse()

        for configuration in sameNameConf :
            # add same name configuration rule children to self child list
            self.addChildren(configuration.extractChildrenByClass([Operator, Rule]), append=False)


    def propagate (self, context=PropagationContext) :
        """propagate proprieties to children

        make needed compositions, join ancestor name to its name,
        and add rules previously defined rules"""

        # make all needed composition
        self.composition(context)

        super().propagate(context)

    def Inheritance (self, context) :
        """make configuration name and rule inheritance"""
        # check for configuration name inheritance
        self.OptionsInheritance(context)

        # check for rule inheritance
        self.ruleInheritance(context)

    def OptionsInheritance (self, context) :
        """make configuration name inheritance """

        context.getConfigurationOptions().append(self.option.copy())
        self.setName(".".join(context.getConfigurationOptions().getOptionItems("Name")))


    def getRootPath (self) :

        paths = self.extractChildrenByClass([Path, GroupPath])

        rootPath = GroupPath()
        rootPath.addChildren(paths)

        return rootPath

    def getConfigurableElements (self) :
        """return all path name defined in this configuration"""

        return self.getRootPath().getPathNames()

    def toPFWScript(self, pfwScriptContext) :
        """Output the PFW commands needed to recreate this configuration

        The PFW commands outputed will recreate this configuration if run
        on a PFW instance"""

        script = ""

        # Copy and update pfwScriptContext for this configuration
        pfwScriptContextAux = pfwScriptContext.copy()
        pfwScriptContextAux.setConfigurationName (self.getName())

        # Add the command to create the configuration
        script += pfwScriptContextAux.getPrefix() + \
                    self.PFWCommandConfiguration + " " + \
                    pfwScriptContextAux.getDomainName() + " " + \
                    pfwScriptContextAux.getConfigurationName() + "\n"

        # encrease prefix
        pfwScriptContextAux.increasePrefix()

        # Create a rootRule
        ruleChildren = self.extractChildrenByClass([Rule, Operator])

        # Do not create a root rule if there is only one fist level Operator rule
        if len(ruleChildren) == 1 and ruleChildren[0].__class__ == Operator :
            ruleroot = ruleChildren[0]

        else :
            ruleroot = Operator()
            ruleroot.setName("ALL")
            ruleroot.addChildren(ruleChildren)


        # Add the command to create the rules of this configuration
        script += ruleroot.toPFWScript(pfwScriptContextAux)


        # Add the command to restore this configuration
        script += pfwScriptContextAux.getPrefix() + \
                    self.PFWCommandRestoreConfiguration + " " + \
                    pfwScriptContextAux.getDomainName() + " " + \
                    pfwScriptContextAux.getConfigurationName() + "\n"

        # Copy pfwScriptContextAux and increase the prefix
        contextAux = pfwScriptContextAux.copy()
        contextAux.increasePrefix()

        # add the parameter settings for this configuration
        paths = self.extractChildrenByClass([Path, GroupPath])
        for path in paths :
            script += path.toPFWScript(contextAux)

        script += pfwScriptContextAux.getPrefix() + \
                    self.PFWCommandSaveConfiguration + " " + \
                    pfwScriptContextAux.getDomainName() + " " + \
                    pfwScriptContextAux.getConfigurationName() + "\n"

        # if domain is sequence aware
        if pfwScriptContextAux.getSequenceAwareness() :

            script += pfwScriptContextAux.getPrefix() + \
                    self.PFWCommandElementSequence + " " + \
                    pfwScriptContextAux.getDomainName() + " " + \
                    pfwScriptContextAux.getConfigurationName() + " "

            for path in paths :
                script += pfwScriptContextAux.getNewLinePrefix() + \
                            path.getName()
            script += "\n"

            script += pfwScriptContextAux.getPrefix() + \
                        self.PFWCommandSequenceAware + " "\
                          + pfwScriptContextAux.getDomainName() + " true \n"

        # for lisibility
        script += "\n"

        return script

    def copy (self) :
        """return a shallow copy of the configuration"""

        # create configuration or subclass copy
        confCopy = self.__class__()

        # add children
        confCopy.children = list(self.children)

        # add option
        confCopy.option = self.option.copy()

        return confCopy

class GroupConfiguration (Configuration) :
    tag = "GroupConfiguration"
    optionNames = ["Name"]
    match = re.compile(r"(supConf|confGroup|confType) *:").match
    childWhiteList = ["Rule", "Operator", "GroupConfiguration", "Configuration", "GroupPath"]

    def composition (self, context) :
        """add itself in context for configuration composition

        Composition is the fact that group configuration with the same name defined
        in a parent will give their rule children to this configuration
        """

        # copyItself
        selfCopy = self.copy()

        # make all needed composition
        super().composition(context)

        # add the copy in context for futur configuration composition
        context.getConfigurations().append(selfCopy)


    def toXML(self, context="") :
        return self.childrenToXML(context)

    def getConfigurableElements (self) :
        """return a list. Each elements consist of a list of configurable element of a configuration

        return a list consisting of all configurable elements for each configuration.
        These configurable elements are organized in a list"""
        configurableElements = []

        configurations = self.extractChildrenByClass([Configuration])
        for configuration in configurations :
            configurableElements.append(configuration.getConfigurableElements())

        groudeConfigurations = self.extractChildrenByClass([GroupConfiguration])
        for groudeConfiguration in groudeConfigurations :
            configurableElements += groudeConfiguration.getConfigurableElements()

        return configurableElements

    def toPFWScript (self, pfwScriptContext) :
        script = ""

        configurationChildren = self.extractChildrenByClass([Configuration, GroupConfiguration])

        for configurationChild in configurationChildren :
            # add configuration settings
            script += configurationChild.toPFWScript(pfwScriptContext)

        return script

# ----------------------------------------------------------

class Domain (ElementWithRuleInheritance, ElementWithTag) :
    tag = "domain"
    sequenceAwareKeyword = "sequenceAware"

    match = re.compile(r"domain *:").match
    optionNames = ["Name", sequenceAwareKeyword]
    childWhiteList = ["Configuration", "GroupConfiguration", "Rule", "Operator"]

    PFWCommandConfigurableElement = "addElement"
    PFWCommandDomain = "createDomain"

    def propagate (self, context=PropagationContext) :
        """ propagate name, sequenceAwareness and rule to children"""

        # call the propagate method of all children
        super().propagate(context)

        self.checkConfigurableElementUnicity()

    def Inheritance (self, context) :
        """check for domain name, sequence awarness and rules inheritance"""
        # check for domain name and sequence awarness inheritance
        self.OptionsInheritance(context)

        # check for rule inheritance
        self.ruleInheritance(context)

    def OptionsInheritance(self, context) :
        """ make domain name and sequence awareness inheritance

        join to the domain name all domain names defined in context and
        if any domain in context is sequence aware, set sequenceAwareness to True"""

        # add domain options to context
        context.getDomainOptions().append(self.option.copy())

        # set name to the junction of all domain name in context
        self.setName(".".join(context.getDomainOptions().getOptionItems("Name")))

        # get sequenceAwareness of all domains in context
        sequenceAwareList = context.getDomainOptions().getOptionItems(self.sequenceAwareKeyword)
        # or operation on all booleans in sequenceAwareList
        sequenceAwareness = False
        for sequenceAware in sequenceAwareList :
            sequenceAwareness = sequenceAwareness or sequenceAware
        # current domain sequenceAwareness = sequenceAwareness
        self.option.setOption(self.sequenceAwareKeyword, sequenceAwareness)


    def extractOptions(self, line) :
        """Extract options from the definition line"""
        options = super().extractOptions(line)

        sequenceAwareIndex = self.optionNames.index(self.sequenceAwareKeyword)

        # translate the keyword self.sequenceAwareKeyword if specified to boolean True,
        # to False otherwise
        try :
            if options[sequenceAwareIndex] == self.sequenceAwareKeyword :
               options[sequenceAwareIndex] = True
            else:
               options[sequenceAwareIndex] = False
        except IndexError :
            options = options + [None] * (sequenceAwareIndex - len(options)) + [False]
        return options

    def getRootConfiguration (self) :
        """return the root configuration group"""
        configurations = self.extractChildrenByClass([Configuration, GroupConfiguration])

        configurationRoot = GroupConfiguration()

        configurationRoot.addChildren(configurations)

        return configurationRoot

    def checkConfigurableElementUnicity (self):
        """ check that all configurable elements defined in child configuration are the sames"""

        # get a list. Each elements of is the configurable element list of a configuration
        configurableElementsList = self.getRootConfiguration().getConfigurableElements()

        # if at least two configurations in the domain
        if len(configurableElementsList) > 1 :

            # get first configuration configurable element list sort
            configurableElementsList0 = list(configurableElementsList[0])
            configurableElementsList0.sort()

            for configurableElements in configurableElementsList :
                # sort current configurable element list
                auxConfigurableElements = list(configurableElements)
                auxConfigurableElements.sort()

                if auxConfigurableElements != configurableElementsList0 :
                    # if different, 2 configurations those not have the same configurable element list
                    # => one or more configurable element is missing in one of the 2 configuration
                    raise UndefinedParameter(self.getName())


    def toPFWScript (self, pfwScriptContext=PFWScriptContext()):
        script = ""

        domainName = self.getName()


        script += pfwScriptContext.getPrefix() + \
                    self.PFWCommandDomain + " " + \
                    domainName + "\n"

        # get sequenceAwareness of this domain
        sequenceAwareness = self.option.getOption(self.sequenceAwareKeyword)

        # Copy and update pfwScriptContext for this domain
        pfwScriptContextAux = pfwScriptContext.copy()
        pfwScriptContextAux.setDomainName(domainName)
        pfwScriptContextAux.setSequenceAwareness(sequenceAwareness)
        pfwScriptContextAux.increasePrefix()

        # get configurable elements
        configurationRoot = self.getRootConfiguration()
        configurableElementsList = configurationRoot.getConfigurableElements()

        # add configurable elements
        if len(configurableElementsList) != 0 :

            for configurableElement in configurableElementsList[0] :

                script += pfwScriptContextAux.getPrefix() + \
                            self.PFWCommandConfigurableElement + " " + \
                            domainName + " " + \
                            configurableElement + "\n"

        # new line to be more lisible :
        script += "\n"

        # add configuration settings
        script += configurationRoot.toPFWScript(pfwScriptContextAux)

        # to be more lisible :
        script += "\n"

        return script


class GroupDomain (Domain) :
    tag = "groupDomain"
    match = re.compile(r"(supDomain|domainGroup) *:").match
    childWhiteList = ["GroupDomain", "Domain", "GroupConfiguration", "Rule", "Operator"]
    def toXML(self, context="") :
        return self.childrenToXML(context)

    def toPFWScript (self, context={}):
        script = ""
        children = self.extractChildrenByClass([Domain, GroupDomain])

        for child in children :
            script += child.toPFWScript(context)

        return script

# ----------------------------------------------------------

class Root(Element):
    tag = "root"
    childWhiteList = ["Domain", "GroupDomain"]
    def toXML(self, context="") :
        return self.childrenToXML(context)


# ===========================================
""" Syntax error Exceptions"""
# ===========================================

class MySyntaxProblems(SyntaxError) :
    comment = "syntax error in %(line)s "

    def __init__(self, line=None, num=None):
        self.setLine(line, num)

    def __str__(self):

        if self.line :
            self.comment = self.comment % {"line" : repr(self.line)}
        if self.num :
            self.comment = "Line " + str(self.num) + ", " + self.comment
        return self.comment

    def setLine (self, line, num):
        self.line = str(line)
        self.num = num


# ---------------------------------------------------------

class MyPropagationError(MySyntaxProblems) :
    """ Syntax error Exceptions used in the propagation step"""
    pass

class UndefinedParameter(MyPropagationError) :
    comment = "Configurations in domain '%(domainName)s' do not all set the same parameters "
    def __init__ (self, domainName):
        self.domainName = domainName
    def __str__ (self):
        return self.comment % { "domainName" : self.domainName }


# -----------------------------------------------------
""" Syntax error Exceptions used by parser"""

class MySyntaxError(MySyntaxProblems) :
    """ Syntax error Exceptions used by parser"""
    pass

class MySyntaxWarning(MySyntaxProblems) :
    """ Syntax warning Exceptions used by parser"""
    pass

class IndentationSyntaxError(MySyntaxError) :
    comment = """syntax error in %(line)s has no father element.
    You can only increment indentation by one tabutation per line")"""

class EmptyLineWarning(MySyntaxWarning):
    comment = "warning : %(line)s is an empty line and has been ommited"

class CommentWarning(MySyntaxWarning):
    comment = "warning : %(line)s is a commentary and has been ommited"

class ChildNotPermitedError(MySyntaxError):
    def __init__(self, line, fatherElement, childElement):
        self.comment = "syntax error in %(line)s, " + fatherElement.tag + " should not have a " + childElement.tag + " child."
        super().__init__(line)


class UnknownElementTypeError(MySyntaxError):
    comment = " error in line %(line)s , not known element type were matched "

class SpaceInIndentationError(MySyntaxError):
    comment = " error in ,%(line)s space is not permited in indentation"


# ============================================
"""Class creating the DOM elements from a stream"""
# ============================================

class ElementsFactory  :
    """Element factory, return an instance of the first matching element

    Test each element list in elementClass and instanciate it if it's methode match returns True
    The method match is called with input line as argument
    """
    def __init__ (self):
        self.elementClass = [
        EmptyLine ,
        Commentary,
        GroupDomain,
        Domain,
        Path,
        GroupConfiguration,
        Configuration,
        Operator,
        Rule,
        GroupPath
        ]

    def createElementFromLine (self, line) :
        """return an instance of the first matching element

        Test each element list in elementClass and instanciate it if it's methode match returns True
        The method match is called with the argument line.
        Raise UnknownElementTypeError if no element matched.
        """
        for element in self.elementClass :
            if element.match(line) :
                # print (line + element.__class__.__name__)
                return element(line)
        # if we have not find any
        raise UnknownElementTypeError(line)

#------------------------------------------------------

class Parser :
    """Class implementing the parser"""
    def __init__(self):
        self.rankPattern = re.compile(r"^([\t ]*)(.*)")
        self.elementFactory = ElementsFactory()
        self.previousRank = 0

    def __parseLine__(self, line):

        rank, rest = self.__getRank__(line)

        # instanciate the coresponding element
        element = self.elementFactory.createElementFromLine(rest)

        self.__checkIndentation__(rank)

        return rank, element

    def __getRank__(self, line):
        """return the rank, the name and the option of the input line

the rank is the number of tabulation (\t) at the line beginning.
the rest is the rest of the line."""
        # split line in rank and rest
        rank = self.rankPattern.match(line)
        if rank :
            rank, rest = rank.group(1, 2)
        else :
            raise MySyntaxError(line)

        # check for empty line
        if rest == "" :
            raise EmptyLineWarning(line)

        # check for space in indentation
        if rank.find(" ") > -1 :
            raise SpaceInIndentationError(line)

        rank = len (rank) + 1  # rank starts at 1


        return rank, rest


    def __checkIndentation__(self, rank):
        """check if indentation > previous indentation + 1. If so, raise IndentationSyntaxError"""
        if (rank > self.previousRank + 1) :
            raise IndentationSyntaxError()
        self.previousRank = rank

    def parse(self, stream, verbose=False):
        """parse a stream, usually a opened file"""
        myroot = Root("root")
        context = [myroot]  # root is element of rank 0
        warnings = ""

        for num, line in enumerate(stream):
            try:
                rank, myelement = self.__parseLine__(line)

                while len(context) > rank :
                    context.pop()
                context.append(myelement)
                context[-2].addChild(myelement)

            except MySyntaxWarning as ex:
                ex.setLine(line, num + 1)
                if verbose :
                    print(ex, file=sys.stderr)

            except MySyntaxError as ex :
                ex.setLine(line, num + 1)
                raise

        return myroot

# ============================
# command line argument parser
# ============================

class ArgparseArgumentParser :
    """class that parse command line arguments with argparse library

    result of parsing are the class atributs"""
    def __init__(self) :

        myArgParser = argparse.ArgumentParser(description='Process domain scripts.')

        myArgParser.add_argument('inputFile', nargs='?',
                                 type=argparse.FileType('r'), default=sys.stdin,
                                 help="the domain script file, default stdin")

        myArgParser.add_argument('-o', '--output',
                                 dest="outputFile",
                                 type=argparse.FileType('w'), default=sys.stdout,
                                 help="the output file, default stdout")

        myArgParser.add_argument('-d', '--debug',
                                 dest="debugFlag",
                                 action='store_true',
                                 help="print debug warnings")


        outputFormatGroupe = myArgParser.add_mutually_exclusive_group(required=False)

        outputFormatGroupe.add_argument('--pfw',
                                        dest="pfwFlag",
                                        action='store_true',
                                        help="output pfw commands (default)")
        outputFormatGroupe.add_argument('--xml',
                                        dest="xmlFlag",
                                        action='store_true',
                                        help="output XML settings (Not fully implemented yet)")
        outputFormatGroupe.add_argument('--raw',
                                        dest="rawFlag",
                                        action='store_true',
                                        help="output raw domain tree (DEBUG ONLY)")


        # process command line arguments
        options = myArgParser.parse_args()

        # maping to atributs
        self.inputFile = options.inputFile
        self.output = options.outputFile

        self.debug = options.debugFlag

        if not (options.pfwFlag or options.xmlFlag or options.rawFlag) :
             # --pfw is default if none provided
             self.pfw = True
             self.xml = self.raw = False
        else :
            self.pfw = options.pfwFlag
            self.xml = options.xmlFlag
            self.raw = options.rawFlag


class OptParseArgumentParser :
    """class that parse command line arguments with optparse library

    result of parsing are the class atributs"""
    def __init__(self) :

        myOptParser = optparse.OptionParser(usage="usage: [-h] [-d] [--pfw | --xml | --raw] "
                                            "[-o OUTPUTFILE] [INPUTFILE]",
                                            description="Process domain scripts")

        myOptParser.add_option('-o', '--output',
                               dest="outputFile", metavar="FILE",
                               help="the output file, default stdout")

        myOptParser.add_option('-d', '--debug',
                               dest="debugFlag",
                               action='store_true',
                               help="print debug warnings")


        outputFormatGroupe = optparse.OptionGroup(myOptParser, "output format")

        outputFormatGroupe.add_option('--pfw',
                                      dest="pfwFlag",
                                      action='store_true',
                                      help="output pfw commands (default)")
        outputFormatGroupe.add_option('--xml',
                                      dest="xmlFlag",
                                      action='store_true',
                                      help="output XML settings (Not fully implemented yet)")
        outputFormatGroupe.add_option('--raw',
                                      dest="rawFlag",
                                      action='store_true',
                                      help="output raw domain tree (DEBUG ONLY)")


        # process command line arguments
        (options, args) = myOptParser.parse_args()

        # If no input file provided, use default one
        if len(args) == 0:
            args = [None]

        # mapping to attributes
        self.inputFile = self.open_secured(args[0], 'r') or sys.stdin
        self.output = self.open_secured(options.outputFile, 'w') or sys.stdout

        self.debug = options.debugFlag

        if not (options.pfwFlag or options.xmlFlag or options.rawFlag) :
             # --pfw is default if none provided
             # TODO: find a way to do that with argparse directly
             self.pfw = True
             self.xml = self.raw = False
        else :
            self.pfw = options.pfwFlag
            self.xml = options.xmlFlag
            self.raw = options.rawFlag

    @staticmethod
    def open_secured(file, openMode="r"):
        if file:
            return open(file, openMode)

        return None

# ==============
# main function
# ==============

def printE(s):
    """print in stderr"""
    print(str(s), file=sys.stderr)

def main ():

    # Get command line arguments
    try:
        imp.find_module("argparse")

    except ImportError:
        printE("Warning: unable to import argparse module, fallback to optparse")
        # Using optparse
        options = OptParseArgumentParser()

    else:
        # Using argparse
        options = ArgparseArgumentParser()

    myparser = Parser()
    try:
        myroot = myparser.parse(options.inputFile, options.debug)

    except MySyntaxError as ex :
        printE(ex)
        printE("EXIT ON FAILURE")
        exit (2)
    else :
        if options.raw :
            options.output.write(str(myroot))
        else :
            try :
                myroot.propagate()

            except MyPropagationError as ex :
                printE(ex)
                printE("EXIT ON FAILURE")
                exit(1)

            else :
                if options.xml :
                    options.output.write(myroot.toXML())

                if options.pfw :
                    options.output.write(myroot.toPFWScript())

# execute main function if the python interpreter is running this module as the main program
if __name__ == "__main__" :
    main()

