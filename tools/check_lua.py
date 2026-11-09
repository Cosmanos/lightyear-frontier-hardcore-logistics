"""Check the runtime Lua scripts before they go into the game.

Compiles every script with Lua 5.4 (the version UE4SS embeds), then reads the compiled bytecode to list the global
names each script uses. A global that is neither standard Lua nor part of the UE4SS API is almost always a typo, or a
local function called above the line that declares it; Lua only reports those when the line runs, in the game.

Usage:  .venv\\Scripts\\python tools/check_lua.py [file or folder ...]     (default: runtime/HardcoreLogistics/Scripts)
Setup:  uv venv .venv  and  uv pip install --python .venv\\Scripts\\python.exe lupa
build_mod.py runs this automatically before installing the runtime mod.
"""
import os
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIR = os.path.join(REPO, "runtime", "HardcoreLogistics", "Scripts")

LUA_GLOBALS = {
    "_G", "_VERSION", "assert", "collectgarbage", "coroutine", "debug", "dofile", "error", "getmetatable", "io",
    "ipairs", "load", "loadfile", "math", "next", "os", "package", "pairs", "pcall", "print", "rawequal", "rawget",
    "rawlen", "rawset", "require", "select", "setmetatable", "string", "table", "tonumber", "tostring", "type",
    "utf8", "warn", "xpcall",
}
UE4SS_GLOBALS = {
    "RegisterHook", "UnregisterHook", "RegisterLoadMapPreHook", "RegisterLoadMapPostHook",
    "RegisterInitGameStatePreHook", "RegisterInitGameStatePostHook", "RegisterBeginPlayPreHook",
    "RegisterBeginPlayPostHook", "RegisterProcessConsoleExecPreHook", "RegisterProcessConsoleExecPostHook",
    "RegisterConsoleCommandHandler", "RegisterConsoleCommandGlobalHandler", "RegisterCustomEvent",
    "UnregisterCustomEvent", "RegisterKeyBind", "IsKeyBindRegistered", "NotifyOnNewObject", "LoopAsync",
    "ExecuteAsync", "ExecuteWithDelay", "ExecuteInGameThread", "FindFirstOf", "FindAllOf", "FindObject",
    "FindObjects", "StaticFindObject", "StaticConstructObject", "LoadAsset", "CreateInvalidObject",
    "ForEachUObject", "IterateGameDirectories", "FName", "FText", "EFindName", "Key", "ModifierKey",
    "ModifierKeys", "PropertyTypes", "EObjectFlags", "EInternalObjectFlags", "ModRef",
    # game-thread timers (present in the installed UE4SS build, driven by the engine tick)
    "LoopInGameThreadWithDelay", "ExecuteInGameThreadWithDelay", "LoopInGameThreadAfterFrames",
    "ExecuteInGameThreadAfterFrames", "CancelDelayedAction",
}

OP_GETTABUP, OP_SETTABUP = 11, 15          # Lua 5.4 opcodes: R[A] := UpValue[B][K[C]] / UpValue[A][K[B]] := RK(C)
ABSLINEINFO = -0x80


class _Dump:
    """Reader for the Lua 5.4 binary chunk format (lundump.c)."""

    def __init__(self, data: bytes):
        self.b, self.p = data, 0

    def byte(self) -> int:
        v = self.b[self.p]
        self.p += 1
        return v

    def size(self) -> int:
        x = 0
        while True:
            c = self.byte()
            x = (x << 7) | (c & 0x7F)
            if c & 0x80:
                return x

    def string(self):
        n = self.size()
        if n == 0:
            return None
        s = self.b[self.p:self.p + n - 1]
        self.p += n - 1
        return s.decode("utf-8", "replace")

    def chunk(self) -> list[tuple[str, int, str]]:
        if self.b[:5] != b"\x1bLua\x54":
            raise ValueError("not a Lua 5.4 chunk")
        self.p = 12                                    # signature, version, format, LUAC_DATA
        if tuple(self.b[12:15]) != (4, 8, 8):
            raise ValueError("unexpected Lua build (instruction/integer/number sizes)")
        self.p = 15 + 16 + 1                           # LUAC_INT, LUAC_NUM, main upvalue count
        out: list[tuple[str, int, str]] = []
        self.function(out)
        return out

    def function(self, out: list) -> None:
        self.string()                                  # source
        line = self.size()                             # linedefined
        self.size()                                    # lastlinedefined
        self.p += 3                                    # numparams, is_vararg, maxstacksize
        n = self.size()
        code = struct.unpack_from(f"<{n}I", self.b, self.p)
        self.p += 4 * n
        consts = []
        for _ in range(self.size()):
            t = self.byte()
            if t in (3, 19):                           # integer, float
                consts.append(None)
                self.p += 8
            elif t in (4, 20):                         # short, long string
                consts.append(self.string())
            else:                                      # nil, false, true
                consts.append(None)
        n = self.size()                                # upvalue descriptors (read the count first: += would
        self.p += 3 * n                                # use self.p from before size() advanced it)
        for _ in range(self.size()):
            self.function(out)                         # nested functions
        n = self.size()
        lineinfo = [x - 256 if x > 127 else x for x in self.b[self.p:self.p + n]]
        self.p += n
        absline = {}
        for _ in range(self.size()):
            pc = self.size()
            absline[pc] = self.size()
        for _ in range(self.size()):                   # local variable names
            self.string()
            self.size()
            self.size()
        upnames = [self.string() for _ in range(self.size())]
        for pc, ins in enumerate(code):
            if pc < len(lineinfo):
                line = absline.get(pc, line) if lineinfo[pc] == ABSLINEINFO else line + lineinfo[pc]
            op, a, b, c = ins & 0x7F, (ins >> 7) & 0xFF, (ins >> 16) & 0xFF, (ins >> 24) & 0xFF
            if op == OP_GETTABUP and b < len(upnames) and upnames[b] == "_ENV" and c < len(consts) and consts[c]:
                out.append((consts[c], line, "reads"))
            elif op == OP_SETTABUP and a < len(upnames) and upnames[a] == "_ENV" and b < len(consts) and consts[b]:
                out.append((consts[b], line, "sets"))


def lua54():
    try:
        import lupa.lua54 as lupa
    except ImportError:
        import lupa
    return lupa.LuaRuntime(encoding=None)


def lua_files(paths: list[str]) -> list[str]:
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith(".lua")]
        else:
            files.append(p)
    return files


def check(lua, paths: list[str]) -> bool:
    compile_ = lua.eval(b"function(src, name) local f, err = load(src, '=' .. name, 't') "
                        b"if not f then return nil, err end return string.dump(f) end")
    allowed = LUA_GLOBALS | UE4SS_GLOBALS
    ok = True
    for path in lua_files(paths):
        name = os.path.basename(path)
        with open(path, "rb") as fh:
            dumped = compile_(fh.read(), name.encode())
        if isinstance(dumped, tuple):
            dumped, err = dumped
        else:
            err = None
        if dumped is None:
            print(f"  SYNTAX  {err.decode('utf-8', 'replace') if isinstance(err, bytes) else err}")
            ok = False
            continue
        unknown = [(g, line, kind) for g, line, kind in _Dump(dumped).chunk() if g not in allowed]
        for g, line, kind in unknown:
            print(f"  GLOBAL  {name}:{line} {kind} '{g}', which is not standard Lua or UE4SS "
                  f"(a typo, or a local used above its declaration?)")
        if unknown:
            ok = False
        else:
            print(f"  ok      {name}")
    return ok


def venv_python():
    p = os.path.join(REPO, ".venv", "Scripts", "python.exe")
    return p if os.path.exists(p) else None


def run_check(paths: list[str]) -> bool:
    """Check from any Python: uses lupa if importable, else the repo's .venv, else skips with a note."""
    try:
        lua = lua54()
    except ImportError:
        py = venv_python()
        if py and os.path.abspath(sys.executable).lower() != os.path.abspath(py).lower():
            sys.stdout.flush()
            return subprocess.run([py, "-I", os.path.abspath(__file__), *paths]).returncode == 0
        print("Lua check skipped: lupa is not installed (see tools/check_lua.py)")
        return True
    print("Lua check (Lua 5.4):")
    return check(lua, paths)


if __name__ == "__main__":
    sys.exit(0 if run_check(sys.argv[1:] or [DEFAULT_DIR]) else 1)
