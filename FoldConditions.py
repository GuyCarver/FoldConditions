import sublime, sublime_plugin
import collections, re

Defines = []
ConditionKeys = "^#(if|else|elif|endif)"
MaxStack = 100

def Defined( aWord, TestDigit = True ) :
  if aWord.isdigit() :
    #TestDigit false means we don't consider digits so we always return True.
    return True if not TestDigit else (aWord != "0")
  return aWord in Defines

def AddWord( aWord ) :
  global Defines
  #Don't ever add digits.
  if not Defined(aWord, False) :
    Defines.append(aWord)
#    print Defines

def RemoveWord( aWord ) :
  global Defines
  Defines.remove(aWord)
#  print Defines

#Create enum for define parsing state.
#free = not currently in a define state.
#defoff = In a define state with a false condition.
#defon = In a define state with a true condition.
free, defoff, defon = range(3)

#1st number is True for defined, False for !defined, bi
ifdefA = [
(True, "#[ \t]*if[ \t]*([0-9]+)"),
(True, "#[ \t]*if[ \t]*defined[ \t]*\((.*)\)"),
(True, "#[ \t]*ifdef[ \t]*(.*)"),
(False, "#[ \t]*if[ \t]*!defined[ \t]*\((.*)\)"),
(False, "#[ \t]*ifndef[ \t]*(.*)")
]

elifA = [
(True, "#[ \t]*elif[ \t]*defined\((.*)\)"),
(False, "#[ \t]*elif[ \t]*!defined\((.*)\)"),
]

class DefineCommand( sublime_plugin.TextCommand ) :
  def run( self, edit, cmd = "add" ) :
    vw = self.view
    runcmd = AddWord if cmd == "add" else RemoveWord
    for s in vw.sel() :
      #Get word under selection and add to list.
      word = vw.word(s.a)
      wordstr = vw.substr(word)
      runcmd(wordstr)

class DefineRemoveSelCommand( sublime_plugin.WindowCommand ) :
  def run( self ) :
    if len(Defines) :
      self.window.show_quick_panel(Defines, self.ondone)

  def ondone( self, aArg ) :
    if aArg != -1 :
      Defines.remove(Defines[aArg])

def IfDef( aLine ) :
  ###Return (T/F = found result, free|defon|defoff)
  for srch in ifdefA :
    res =  re.search(srch[1], aLine)
    if res :
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      # print "def: %s = %s" % (aLine, defd)
      return(True, defon if defd else defoff)
  return (False, free)

def Else( aLine ) :
  res = re.search("#[ \t]*else", aLine)
  # if res :
    # print "else: %s" % aLine
  return res != None

def ElIf( aLine ) :
  ###Return (T/F = found result, free|defon|defoff)
  for srch in elifA :
    res =  re.search(srch[1], aLine)
    if res :
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      # print "elif: %s = %s" % (aLine, defd)
      return(True, defon if defd else defoff)
  return (False, free)

def EndIf( aLine ) :
  res = re.search("#[ \t]*endif", aLine)
  # if res :
    # print "endif: %s" % aLine
  return res != None

def ShouldFold( state1, state2 ) :
  return state1 != state2 and (state1 == defoff or state2 == defoff)

class FoldConditionsCommand( sublime_plugin.TextCommand ) :
  def __init__( self, edit ) :
    super(FoldConditionsCommand, self).__init__(edit)
    self.expand = []
    self.fold = []
    self.startPoint = 0
    self.stack = collections.deque([], MaxStack)

  def AddRegion( self, line, aState ) :
    reg = sublime.Region(self.startPoint, line.a - 1)
    rc1 = self.view.rowcol(reg.a)
    rc2 = self.view.rowcol(reg.b)
    if aState != defoff:
      self.expand.append(reg)
      # print "expand: %s - %s" % (rc1, rc2)
    else:
      self.fold.append(reg)
      # print "fold: %s - %s" % (rc1, rc2)

    # print "State: %d" % aState
    self.startPoint = line.b

  def Push( self, aState, aLine ) :
    prevState = free if len(self.stack) == 0 else self.stack[-1]
    self.stack.append(aState)
    if ShouldFold(prevState, aState) :
      self.AddRegion(aLine, prevState)

  def Pop( self, aLine ) :
    state = free if len(self.stack) == 0 else self.stack.pop()
    prevState = free if len(self.stack) == 0 else self.stack[-1]
    if ShouldFold(prevState, state) :
      self.AddRegion(aLine, state)

  def FindRegions( self ) :
    vw = self.view
    conditionRegs = vw.find_all(ConditionKeys)
    for r in conditionRegs :
      ln = vw.line(r)
      txt = vw.substr(ln)
      defd, state = IfDef(txt)
      if defd :
        #if define then create a stack entry.
        self.Push(state, ln)
      elif Else(txt) :
        #if else then swap the stack entry state
        self.Pop(ln)
        self.Push(state, ln)
      elif EndIf(txt) :
        #if endif then pop the stack entry.
        self.Pop(ln)
      else:
        defd, state = ElIf(txt)
        if defd :
          #if elif then pop the stack entry and make a new one.
          self.Pop(ln)
          self.Push(state, ln)

  def reset( self ) :
    self.startPoint = 0
    self.expand = [ ]
    self.fold = [ ]
    self.stack.clear()

  def run( self, edit ) :
    self.reset()
    self.FindRegions()
    vw = self.view

    vw.fold(self.fold)
    vw.unfold(self.expand)
    self.reset()
