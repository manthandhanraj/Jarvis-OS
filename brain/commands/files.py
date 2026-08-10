"""File management commands (Day 13). Every command needs a file/folder signal
so it never steals a plain 'open <app>' request."""
from __future__ import annotations

import re

from automation.files.file_manager import _ROOT_ALIASES
from automation.windows.service import WindowsAutomationService
from brain.commands.base import Command, CommandContext, CommandResult
from core.risk import RiskLevel
from utils.text import has_keyword, normalize, strip_triggers

_ROOT_WORDS: tuple[str, ...] = tuple(_ROOT_ALIASES)
_FILE_FILLER = ("file", "files", "folder", "the", "ko", "named", "called",
                "mera", "meri", "mere", "my", "wala")
_SEP = re.compile(r"\b(?:to|into)\b")


def _has_root(text: str) -> bool:
    return has_keyword(text, _ROOT_WORDS)


def _has_file_signal(text: str) -> bool:
    return has_keyword(text, ("file", "files", "folder")) or _has_root(text)


class _FileCommand(Command):
    def __init__(self, service: WindowsAutomationService) -> None:
        self.service = service

    @property
    def files(self):
        return self.service.files


class FindFilesCommand(_FileCommand):
    name = "find_files"
    description = "Search for a file or folder"
    risk = RiskLevel.SAFE
    canonical = "find file {target}"
    target_hint = "name or part of a file/folder name"
    _triggers = ("find file", "search file", "file dhundo", "dhundo file",
                 "locate", "kaunsi file", "where is", "file kahan", "koi file",
                 "search for file", "find files")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers) and _has_file_signal(text)

    def _query(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("find", "search", "dhundo", "locate"),
                              extra_filler=_FILE_FILLER + ("where", "kahan", "is"))

    def describe(self, text: str) -> str:
        return f"Search for '{self._query(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        query = self._query(text)
        if not query:
            return CommandResult("Kaunsi file dhundu? Naam batao.")
        return CommandResult(self.files.search_files(query).message)


class OpenFileCommand(_FileCommand):
    name = "open_file"
    description = "Open a file or a folder"
    risk = RiskLevel.SAFE
    canonical = "open file {target}"
    target_hint = "file name, or a folder like downloads/documents"
    _triggers = ("open", "kholo", "khol", "open karo", "khol do")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers) and _has_file_signal(text)

    def _target(self, text: str) -> str:
        return strip_triggers(text, self._triggers, extra_filler=_FILE_FILLER)

    def describe(self, text: str) -> str:
        return f"Open '{self._target(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        target = self._target(text)
        if not target:
            return CommandResult("Kaunsi file ya folder kholun?")
        return CommandResult(self.files.open_item(target).message)


class ListFolderCommand(_FileCommand):
    name = "list_folder"
    description = "List what's inside a folder"
    risk = RiskLevel.SAFE
    canonical = "list folder {target}"
    target_hint = "folder name, e.g. downloads"
    _triggers = ("list folder", "show files in", "folder me kya", "kya hai folder",
                 "contents of", "list files", "folder ke files", "show folder",
                 "kya rakha hai", "me kya", "mein kya", "kya hai", "kitni files",
                 "kitne files", "kya rakha")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers) and _has_file_signal(text)

    def _target(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("list", "show", "contents", "of", "in"),
                              extra_filler=_FILE_FILLER + ("kya", "hai", "me", "mein", "rakha"))

    def describe(self, text: str) -> str:
        return f"List folder '{self._target(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        target = self._target(text) or "downloads"
        return CommandResult(self.files.list_folder(target).message)


class CreateFolderCommand(_FileCommand):
    name = "create_folder"
    description = "Create a new folder"
    risk = RiskLevel.MEDIUM
    canonical = "create folder {target}"
    target_hint = "name for the new folder"
    _triggers = ("create folder", "make folder", "new folder", "folder banao",
                 "folder bana do", "banado folder", "create directory")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def _target(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("create", "make", "banao", "bana"),
                              extra_filler=("folder", "directory", "named", "called",
                                            "naam", "the", "ek"))

    def describe(self, text: str) -> str:
        return f"Create folder '{self._target(text)}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        name = self._target(text)
        if not name:
            return CommandResult("Folder ka naam batao.")
        return CommandResult(self.files.create_folder(name).message)


class _TransferCommand(_FileCommand):
    verbs: tuple[str, ...] = ()
    action: str = "move"

    def matches(self, text: str) -> bool:
        if not has_keyword(text, self.verbs):
            return False
        return _has_root(text) or bool(_SEP.search(normalize(text)))

    def _parse(self, text: str) -> tuple[str, str]:
        t = normalize(text)
        t = re.sub(
            r"\b(move|copy|paste|shift|karo|kardo|kar|do|please|daal|daalo|daaldo|dal)\b",
            " ", t,
        )
        dest_alias = next((a for a in _ROOT_WORDS if re.search(rf"\b{re.escape(a)}\b", t)), None)
        if dest_alias:
            t = re.sub(rf"\b{re.escape(dest_alias)}\b", " ", t)
            t = re.sub(r"\b(to|into|me|mein|folder|ko|the|in)\b", " ", t)
            return " ".join(t.split()).strip(" .,-"), dest_alias
        parts = _SEP.split(t, maxsplit=1)
        if len(parts) == 2:
            src = " ".join(parts[0].split()).strip(" .,-")
            dest = " ".join(re.sub(r"\bfolder\b", " ", parts[1]).split()).strip(" .,-")
            return src, dest
        return "", ""

    def describe(self, text: str) -> str:
        src, dest = self._parse(text)
        return f"{self.action.title()} '{src}' to '{dest}'"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        src, dest = self._parse(text)
        if not src or not dest:
            return CommandResult(
                f"{self.action.title()} ke liye batao: source aur destination. "
                f"Jaise 'resume.pdf ko documents me {self.action} karo'."
            )
        if self.action == "copy":
            return CommandResult(self.files.copy_item(src, dest).message)
        return CommandResult(self.files.move_item(src, dest).message)


class MoveFileCommand(_TransferCommand):
    name = "move_file"
    description = "Move a file or folder into another folder"
    risk = RiskLevel.MEDIUM
    canonical = "move {target}"
    target_hint = "source and destination, e.g. 'report.pdf to documents'"
    verbs = ("move", "shift", "hatao")
    action = "move"


class CopyFileCommand(_TransferCommand):
    name = "copy_file"
    description = "Copy a file or folder into another folder"
    risk = RiskLevel.MEDIUM
    canonical = "copy {target}"
    target_hint = "source and destination, e.g. 'report.pdf to backup'"
    verbs = ("copy", "duplicate", "copy karo")
    action = "copy"


class DeleteFileCommand(_FileCommand):
    name = "delete_file"
    description = "Delete a file or folder (to Recycle Bin)"
    risk = RiskLevel.HIGH
    canonical = "delete file {target}"
    target_hint = "file or folder name to delete"
    _triggers = ("delete file", "remove file", "file delete", "delete folder",
                 "remove folder", "file hata do", "file hatao", "trash file",
                 "file mita do", "delete the file")

    def matches(self, text: str) -> bool:
        if not has_keyword(text, ("delete", "remove", "hata", "trash", "mita")):
            return False
        return _has_file_signal(text)

    def _target(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("delete", "remove", "hata", "trash", "mita"),
                              extra_filler=_FILE_FILLER + ("do", "do",))

    def describe(self, text: str) -> str:
        return f"Delete '{self._target(text)}' (moves to Recycle Bin)"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        target = self._target(text)
        if not target:
            return CommandResult("Kaunsi file delete karun? Naam batao.")
        return CommandResult(self.files.delete_item(target).message)


class OrganizeFolderCommand(_FileCommand):
    name = "organize_folder"
    description = "Organize a folder by file type"
    risk = RiskLevel.MEDIUM
    canonical = "organize {target}"
    target_hint = "folder to organize, e.g. downloads"
    _triggers = ("organize", "clean up", "cleanup", "sort files", "sort folder",
                 "organize karo", "saaf karo", "arrange files")

    def matches(self, text: str) -> bool:
        return has_keyword(text, self._triggers)

    def _target(self, text: str) -> str:
        return strip_triggers(text, self._triggers + ("organize", "sort", "arrange", "clean"),
                              extra_filler=("folder", "files", "the", "my", "up", "karo"))

    def describe(self, text: str) -> str:
        return f"Organize '{self._target(text) or 'downloads'}' by file type"

    def execute(self, text: str, ctx: CommandContext) -> CommandResult:
        target = self._target(text) or "downloads"
        return CommandResult(self.files.organize(target).message)


def build_file_commands(service: WindowsAutomationService) -> list[Command]:
    """Order matters: specific verbs first; open/find are broad so keep them
    guarded by the file/folder signal in matches()."""
    return [
        DeleteFileCommand(service),
        MoveFileCommand(service),
        CopyFileCommand(service),
        CreateFolderCommand(service),
        OrganizeFolderCommand(service),
        ListFolderCommand(service),
        FindFilesCommand(service),
        OpenFileCommand(service),
    ]
