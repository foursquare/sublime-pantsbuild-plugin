import os.path as P
import sublime, sublime_plugin

class OpenBuildCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    path = P.join(P.dirname(self.view.file_name()), 'BUILD')
    print('>>>>', path)
    if P.exists(path):
      self.view.window().open_file(path)
    else:
      print('NO EXIST ', path)