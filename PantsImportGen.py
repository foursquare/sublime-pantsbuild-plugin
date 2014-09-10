import sublime, sublime_plugin

from collections import defaultdict
import json
import os
import subprocess


class PantsImportInsertCommand(sublime_plugin.TextCommand):

  def run(self, edit, imports):
    first_import = self.view.find("import", 0)
    package = self.view.find("^\s*package\s+[^\n]+$", 0)
    insertion_point = 0
    if first_import:
      insertion_point = first_import.begin()
    elif package:
      insertion_point = package.end() + 1
      insertion_point += self.view.insert(edit, insertion_point, "\n")
    content = "".join(["import " + i + "\n" for i in sorted(imports)])
    self.view.insert(edit, insertion_point, content)


class PantsImportGenCommand(sublime_plugin.TextCommand):

  def find_pwd(self):
    pwd, _ = os.path.split(os.path.abspath(self.view.file_name()))
    while pwd:
      print(pwd)
      if os.path.isfile(os.path.join(pwd, 'fs')):
        return pwd
      pwd, _ = os.path.split(pwd)
    # TODO(dan): Alert.
    print("Where is your pants!?")

  def multi_select_callback(self, new_imports, ambiguous_new_import, ambiguous_new_imports, i):
    if i != -1:
      new_imports.append(ambiguous_new_import[1][i])
    if len(ambiguous_new_imports) == 0:
      self.view.run_command("pants_import_insert", {"imports" : new_imports})
      return
    next_ambiguous_new_import = ambiguous_new_imports.pop(0)
    callback = lambda i: self.multi_select_callback(new_imports, next_ambiguous_new_import, ambiguous_new_imports, i)
    sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(next_ambiguous_new_import[1], callback), 10)

  def run(self, edit):
    symbols = set()
    for selector in ['entity.name.class', 'entity.other.inherited-class']:
      for i in self.view.find_by_selector(selector):
        if self.view.substr(i.begin() - 1) == ".":
          continue
        raw_symbol = self.view.substr(i)
        symbol = raw_symbol.split(".")[0]
        symbols.add(symbol)

    if len(symbols):
      command = ["./fs", "importgen", "--importgen-file=" + self.view.file_name()]
      for symbol in symbols:
        command.append("--importgen-symbol=" + symbol)
      detail = json.loads(subprocess.check_output(command, cwd=self.find_pwd()).decode("UTF-8"))
    else:
      detail = {}

    new_imports = []
    ambiguous_new_imports = []
    for symbol in symbols:
      if symbol in detail:
        completions = detail[symbol]
        if len(completions) == 1:
          if len(completions[0]):
            new_imports.append(completions[0])
          else:
            # print("already have " + symbol)
            pass
        elif len(completions) > 1:
          ambiguous_new_imports.append((symbol, completions))
        else:
          # print("unknown " + symbol)
          pass
    self.multi_select_callback(new_imports, [], ambiguous_new_imports, -1)

