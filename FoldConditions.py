import sublime, sublime_plugin
import collections, re

Defines = []
ConditionKeys = "^#[.\t]*(if|else|elif|endif)"
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
    # print(Defines)

def RemoveWord( aWord ) :
  global Defines
  try:
    Defines.remove(aWord)
    # print(Defines)
  except:
    pass

#Create enum for define parsing state.
#free = not currently in a define state.
#defoff = In a define state with a false condition.
#defon = In a define state with a true condition.
free, defoff, defon = range(3)

def OpOr( aValue1, aValue2 ) :
  # print("{} or {}".format(aValue1, aValue2))
  return aValue1 or aValue2

def OpAnd( aValue1, aValue2 ) :
  # print("{} and {}".format(aValue1, aValue2))
  return aValue1 and aValue2

moredefA = [
(True, re.compile("[ \t]*\|\|[ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)"), OpOr),
(False, re.compile("[ \t]*\|\|[ \t]*![ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)"), OpOr),
(True, re.compile("[ \t]*&&[ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)"), OpAnd),
(False, re.compile("[ \t]*&&[ \t]*![ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)"), OpAnd)
]

#1st number is True for defined, False for !defined, bi
ifdefA = [
(True, re.compile("#[ \t]*if[ \t]*([0-9]+)")),
(True, re.compile("#[ \t]*if[ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)")),
(True, re.compile("#[ \t]*ifdef[ \t]*([a-zA-Z0-9]+)")),
(False, re.compile("#[ \t]*if[ \t]*!defined[ \t]*\(([a-zA-Z0-9]+)\)")),
(False, re.compile("#[ \t]*ifndef[ \t]*([a-zA-Z0-9]+)"))
]

elifA = [
(True, re.compile("#[ \t]*elif[ \t]*defined\((.*)\)")),
(False, re.compile("#[ \t]*elif[ \t]*!defined\((.*)\)")),
]

elsesearch = re.compile("#[ \t]*else.*")
endifsearch = re.compile("#[ \t]*endif.*")

class DefineCommand( sublime_plugin.TextCommand ) :
  def run( self, edit, cmd = "add" ) :
    vw = self.view
    runcmd = AddWord if cmd == "add" else RemoveWord
    for s in vw.sel() :
      #Get word under selection and add to list.
      word = vw.word(s.a)
      wordstr = vw.substr(word)
      runcmd(wordstr)

    # when adding/removing a define run the fold.
    vw.run_command("fold_conditions")

class DefineRemoveSelCommand( sublime_plugin.WindowCommand ) :
  def run( self ) :
    if len(Defines) :
      self.window.show_quick_panel(Defines, self.ondone)

  def ondone( self, aArg ) :
    if aArg != -1 :
      Defines.remove(Defines[aArg])

def CheckMore( aValue, aLine ) :
  if aLine == "" :
    return aValue

  # print("Checking more " + aLine)
  for srch in moredefA :
    res = srch[1].search(aLine)
    if res and res.lastindex :
      # print("Matched {} checkmore {}".format(res.group(1), res.lastindex))
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      if res.lastindex == 2 :
        CheckMore(defd, res.group(2))
      aValue = srch[2](aValue, defd)

  return aValue

def IfDef( aLine ) :
  ###Return (T/F = found result, free|defon|defoff)
  for srch in ifdefA :
    res =  srch[1].search(aLine)
    if res and res.lastindex :
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      # print("{} last index {}".format(res.group(1), res.lastindex))
      if res.lastindex == 2 :
        defd = CheckMore(defd, res.group(2))
      # print("def: {} = {}".format(aLine, defd))
      return(True, defon if defd else defoff)
  return (False, free)

def Else( aLine ) :
  res = elsesearch.search(aLine)
  # if res :
    # print("else: " + aLine)
  return res != None

def ElIf( aLine ) :
  ###Return (T/F = found result, free|defon|defoff)
  for srch in elifA :
    res =  srch[1].search(aLine)
    if res :
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      # print("elif: {} = {}".format(aLine, defd))
      return(True, defon if defd else defoff)
  return (False, free)

def EndIf( aLine ) :
  res = endifsearch.search(aLine)
  # if res :
    # print("endif: " + aLine)
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
      # print("expand: {} - {}".format(rc1, rc2))
    else:
      self.fold.append(reg)
      # print("fold: {} - {}".format(rc1, rc2))

    # print("State: " + str(aState))
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
    return state

  def FindRegions( self ) :
    vw = self.view
    #Find all of the lines we need to process.
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
        state = self.Pop(ln)
        # print("else: " + str(state))
        self.Push(defon if state == defoff else defoff, ln)
      elif EndIf(txt) :
        #if endif then pop the stack entry.
        state = self.Pop(ln)
      else:
        defd, state = ElIf(txt)
        if defd :
          #if elif then pop the stack entry and make a new one.
          prevState = self.Pop(ln)
          #Only use the new state if the previous state was false
          # otherwise this state should be off.
          self.Push(defoff if prevState == defon else state, ln)

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
