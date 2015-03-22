import sublime, sublime_plugin
import collections, re, functools

Defines = []
MaxStack = 100

def dbgprint ( *aArgs ) :
#  print(*aArgs)
  pass

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
#    dbgprint(Defines)

def ToggleWord( aWord ) :
  global Defines
  if Defined(aWord, False) :
    try:
      Defines.remove(aWord)
    except:
      pass
  else:
    Defines.append(aWord)

def RemoveWord( aWord ) :
  global Defines
  try:
    Defines.remove(aWord)
#    dbgprint(Defines)
  except:
    pass

#Create enum for define parsing state.
#free = not currently in a define state.
#defoff = In a define state with a false condition.
#defon = In a define state with a true condition.
defon, defoff = range(2)

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
(False, re.compile("[ \t]*&&[ \t]*![ \t]*defined[ \t]*\(([a-zA-Z0-9]+)\)(.*)"), OpAnd),
]

#1st number is True for defined, False for !defined, bi
ifdefA = [
(True, re.compile("#[ \t]*if[ \t]*defined[ \t]*\(([_a-zA-Z0-9]+)\)(.*)")),
(True, re.compile("#[ \t]*ifdef[ \t]*([_a-zA-Z0-9]+)")),
(False, re.compile("#[ \t]*if[ \t]*!defined[ \t]*\(([_a-zA-Z0-9]+)\)")),
(False, re.compile("#[ \t]*ifndef[ \t]*([_a-zA-Z0-9]+)")),
(True, re.compile("#[ \t]*if[ \t]*([\(\)0-9a-zA-Z_]+)"))
]

elifA = [
(True, re.compile("#[ \t]*elif[ \t]*defined\((.*)\)")),
(False, re.compile("#[ \t]*elif[ \t]*!defined\((.*)\)")),
]

elsesearch = re.compile("#[ \t]*else.*")
endifsearch = re.compile("#[ \t]*endif.*")

class DefineCommand( sublime_plugin.TextCommand ) :
  def run( self, edit, cmd = "toggle" ) :
    vw = self.view
#    dbgprint("running")
    if cmd == 'add' :
      runcmd = AddWord
    elif cmd == 'toggle' :
      runcmd = ToggleWord
    else:
      runcmd = RemoveWord

    for s in vw.sel() :
      #Get word under selection and add to list.
      word = vw.word(s.a)
      wordstr = vw.substr(word)
      runcmd(wordstr)

    # when adding/removing a define run the fold.
    vw.run_command("fold_conditions")

class DefineRemoveSelCommand( sublime_plugin.TextCommand ) :
  def run( self, edit ) :
    if len(Defines) :
      self.view.window().show_quick_panel(Defines, self.ondone)

  def ondone( self, aArg ) :
    if aArg != -1 :
      Defines.remove(Defines[aArg])
      self.view.run_command("fold_conditions")

def CheckMore( aValue, aLine ) :
  if aLine == "" :
    return aValue

#  dbgprint("Checking more " + aLine)
  for srch in moredefA :
    res = srch[1].search(aLine)
    if res and res.lastindex :
#      dbgprint("Matched {} checkmore {}".format(res.group(1), res.lastindex))
      defd = srch[0] if Defined(res.group(1)) else not srch[0]
      if res.lastindex == 2 :
        CheckMore(defd, res.group(2))
      aValue = srch[2](aValue, defd)

  return aValue

NodeStack = None #Stack of state, Eval, Sibling, Child
view = None

def PushChild( aState, aRange, aEval ) :
  global NodeStack
  node = (aState, aRange, aEval, [], [])
  NodeStack[0][4].insert(0, node)
  NodeStack.insert(0, node)

def Pop( ) :
  global NodeStack
  if len(NodeStack) > 1 :
    NodeStack.pop(0)
    return True
  return False

def PushSibling( aState, aRange, aEval, aPush = True ) :
  global NodeStack
  node = (aState, aRange, aEval, [], [])
  NodeStack[0][3].insert(0, node)
  res = Pop()
  if (aPush):
    NodeStack.insert(0, node)
  return res

def EvalFree( aRange, aHidden ) :
  dbgprint("open")
  return 0

def EvalIf( OnOff, aRes, aRange, aHidden ) :
  defd = OnOff if Defined(aRes.group(1)) else not OnOff
#  dbgprint("{} last index {}".format(res.group(1), res.lastindex))
  if aRes.lastindex == 2 :
    defd = CheckMore(defd, aRes.group(2))
  dbgprint(aRange, aRes.group(0), defd)
  return int(not defd)

def EvalElIf( OnOff, aRes, aRange, aHidden ) :
  res = (aHidden ^ 1) << 1
  if not res:
    defd = OnOff if Defined(aRes.group(1)) else not OnOff
    res = int(not defd)
  dbgprint(aRange, aRes.group(0), res)
  return res

def EvalElse( aRange, aHidden ) :
  ln = view.line(aRange)
  line = view.substr(ln)
  dbgprint(aRange, line, aHidden)
  return aHidden ^ 1

def EvalEndIf( aRange, aHidden ) :
  aHidden = 0
  ln = view.line(aRange)
  line = view.substr(ln)
  dbgprint(aRange, line, aHidden)
  return aHidden

def IfDef( aRange, aLine ) :
  for srch in ifdefA :
    res = srch[1].search(aLine)
    if res and res.lastindex :
      PushChild(ifstate, aRange, functools.partial(EvalIf, srch[0], res))
      return True
  return False

def ElIf( aRange, aLine ) :
  for srch in elifA :
    res =  srch[1].search(aLine)
    if res :
      return PushSibling(ifstate, aRange, functools.partial(EvalElIf, srch[0], res))
    return False

def Else( aRange, aLine ) :
  res = elsesearch.search(aLine)
  if res != None :
    return PushSibling(elsestate, aRange, EvalElse)
  return False

def EndIf( aRange, aLine ) :
  res = endifsearch.search(aLine)
  if res != None :
    return PushSibling(freestate, aRange, EvalEndIf, False)
  return False

def freestate( aRange, aLine ) :
  res = None
  if not IfDef(aRange, aLine) :
    if (Else(aRange, aLine)) or (ElIf(aRange, aLine)) or (EndIf(aRange, aLine)):
      res = "Unmatched condition"
  return res

def ifstate( aRange, aLine ) :
  if not IfDef(aRange, aLine):
    if not Else(aRange, aLine):
      if not ElIf(aRange, aLine):
        EndIf(aRange, aLine)
  return None

def elsestate( aRange, aLine ) :
  if not IfDef(aRange, aLine):
      if not ElIf(aRange, aLine):
        if not EndIf(aRange, aLine):
          if Else(aRange, aLine):
            return "Nested Else"
  return None

class FoldConditionsCommand( sublime_plugin.TextCommand ) :
  def __init__( self, edit ) :
    super(FoldConditionsCommand, self).__init__(edit)
    self.reset()

  def AddFold( self, aRegion ) :
    r = sublime.Region(self.startPoint, max(aRegion.begin() - 1, 0))
    self.fold.append(r)
    dbgprint("fold", r)
    self.startPoint = aRegion.end() + 1
    self.Folding = False

  def AddExpand( self, aRegion ) :
    dbgprint("expand", aRegion)
    self.startPoint = aRegion.end() + 1
    self.Folding = True

  def crawl( self, aState, aHidden ):
    aHidden = aState[2](aState[1], aHidden)
#    dbgprint(aHidden)

    if not aHidden :
      if self.Folding :
        self.AddFold(aState[1])

      for child in aState[4]:
        self.crawl(child, aHidden)
    else:
      if not self.Folding:
        self.AddExpand(aState[1])

    for sibling in aState[3]:
      aHidden = self.crawl(sibling, aHidden)

  def FindRegions( self ) :
    global view
    global NodeStack
    view = self.view
    NodeStack = [(freestate, None, EvalFree, [], [])] #Stack of state, Region, Eval, Sibling, Child

    conditionRegs = view.find_by_selector("preprocessor.keyword.control.import.c")
    conditionRegs = conditionRegs + view.find_by_selector("preprocessor.import.control.keyword.c")
    conditionRegs = sorted(conditionRegs, key = lambda r: r.begin())

    for r in conditionRegs:
      ln = view.line(r)
      line = view.substr(ln)
#      dbgprint(view.rowcol(ln.begin()), line)
      res = NodeStack[0][0](ln, line)
      if res :
        row, _ = view.rowcol(ln.begin())
        msg = "{} line {} - {}".format(res, row + 1, line)
        dbgprint(msg)
        view.show_at_center(ln)
        view.sel().clear()
        view.sel().add(ln)
        sublime.error_message(msg)
        return

  def reset( self ) :
    global NodeStack
    global view
    self.startPoint = 0
    self.fold = [ ]
    self.Folding = False
    NodeStack = None
    view = None

  def run( self, edit ) :
    vw = self.view
    self.reset()
    vw.run_command("unfold_all")
    self.FindRegions()

    if (len(NodeStack) > 1):
      for s in NodeStack[:-1] :
        ln = vw.line(s[1])
        row, _ = vw.rowcol(ln.begin())
        line = vw.substr(ln)
        print("Unclosed condition", row + 1, line)
    else:
      self.crawl(NodeStack[0], 0)

    vw.fold(self.fold)
    self.reset()
