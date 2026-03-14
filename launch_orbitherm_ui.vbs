Set objShell = CreateObject("Wscript.Shell")
objShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.Run "pythonw orbitherm_ui.py", 0, False