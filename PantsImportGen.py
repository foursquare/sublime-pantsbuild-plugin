import sublime, sublime_plugin

from collections import defaultdict
import json
import os
import subprocess
import tempfile
import threading


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


class PantsImportGenCall(threading.Thread):
    def __init__(self, pwd, file_path, symbols):
        self.pwd = pwd
        self.file_path = file_path
        self.symbols = symbols
        threading.Thread.__init__(self)

    def run(self):
      command = ["./pants", "importgen", "--importgen-file=" + self.file_path]
      for symbol in self.symbols:
        command.append("--importgen-symbol=" + symbol)
      self.detail = json.loads(subprocess.check_output(command, cwd=self.pwd).decode("UTF-8"))


class PantsImportGenCommand(sublime_plugin.TextCommand):

  def find_pwd(self):
    pwd, _ = os.path.split(os.path.abspath(self.view.file_name()))
    while pwd:
      if os.path.isfile(os.path.join(pwd, 'fs')):
        return pwd
      pwd, _ = os.path.split(pwd)
    # TODO(dan): Alert.
    print("Where is your pants!?")

  def multi_select_callback(self, new_imports, already_imported_symbols, unknown_symbols, ambiguous_new_import, ambiguous_new_imports, i):
    if i != -1:
      new_imports.append(ambiguous_new_import[1][i])
    if len(ambiguous_new_imports) == 0:
      self.view.set_status('pants_import_gen', 'Pants Import Gen [New=%d Unknown=%d Existing=%d]' % (len(new_imports), len(already_imported_symbols), len(unknown_symbols)))
      self.view.run_command("pants_import_insert", {"imports" : new_imports})
      return
    next_ambiguous_new_import = ambiguous_new_imports.pop(0)
    callback = lambda i: self.multi_select_callback(new_imports, already_imported_symbols, unknown_symbols, next_ambiguous_new_import, ambiguous_new_imports, i)
    sublime.set_timeout(lambda: sublime.active_window().show_quick_panel(next_ambiguous_new_import[1], callback), 10)

  def run(self, edit):
    self.temp_file = tempfile.NamedTemporaryFile()

    symbols = set()
    for selector in ['entity.name.class', 'entity.other.inherited-class']:
      for i in self.view.find_by_selector(selector):
        if self.view.substr(i.begin() - 1) == ".":
          continue
        raw_symbol = self.view.substr(i)
        symbol = raw_symbol.split(".")[0]
        symbols.add(symbol)

    if len(symbols):
      self.temp_file.write(bytes(self.view.substr(sublime.Region(0, self.view.size())), "UTF-8"))
      thread = PantsImportGenCall(self.find_pwd(), self.temp_file.name, symbols)
      thread.start()
      self.handle_threads([thread], symbols)

  def parse_imports_from_detail(self, symbols, detail):
    new_imports = []
    ambiguous_new_imports = []
    already_imported_symbols = []
    unknown_symbols = []
    for symbol in symbols:
      if symbol in detail:
        completions = detail[symbol]
        if len(completions) == 1:
          if len(completions[0]):
            new_imports.append(completions[0])
          else:
            already_imported_symbols.append(symbol)
        elif len(completions) > 1:
          ambiguous_new_imports.append((symbol, completions))
        else:
          unknown_symbols.append(symbol)
    self.multi_select_callback(new_imports, already_imported_symbols, unknown_symbols, [], ambiguous_new_imports, -1)

  # handle_threads courtesy of https://github.com/wbond/sublime_prefixr/blob/master/Prefixr.py
  def handle_threads(self, threads, symbols, offset=0, i=0, dir=1):
    next_threads = []
    for thread in threads:
      if thread.is_alive():
        next_threads.append(thread)
        continue
      self.parse_imports_from_detail(symbols, thread.detail)
    threads = next_threads

    if len(threads):
      # This animates a little activity indicator in the status area
      before = i % 8
      after = (7) - before
      if not after:
          dir = -1
      if not before:
          dir = 1
      i += dir
      self.view.set_status('pants_import_gen', 'Pants Import Gen [%s=%s]' % (' ' * before, ' ' * after))
      sublime.set_timeout(lambda: self.handle_threads(threads, symbols, offset, i, dir), 100)
      return

    self.view.erase_status('pants_import_gen')
