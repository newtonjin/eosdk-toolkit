"""Parser PE32+ reutilizavel para EOSLANKit."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


class PEParseError(ValueError):
    pass


@dataclass
class Section:
    name: str
    virtual_address: int
    virtual_size: int
    raw_size: int
    raw_offset: int


@dataclass
class DelayImportFunc:
    name: str
    iat_rva: int
    index: int


@dataclass
class DelayImportModule:
    dll_name: str
    functions: list[DelayImportFunc]


class PEFile:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        self._parse()

    # ---- helpers com bounds check ----
    def _safe_unpack(self, fmt: str, off: int) -> tuple | None:
        size = struct.calcsize(fmt)
        if off < 0 or off + size > len(self.data):
            return None
        return struct.unpack_from(fmt, self.data, off)

    def _in_bounds(self, off: int, size: int = 1) -> bool:
        return 0 <= off and off + size <= len(self.data)

    def _parse(self) -> None:
        if len(self.data) < 0x40 or self.data[:2] != b"MZ":
            raise PEParseError(f"Nao e PE: {self.path}")

        pe_off_t = self._safe_unpack("<I", 0x3C)
        if pe_off_t is None:
            raise PEParseError("MZ header truncado")
        pe_off = pe_off_t[0]

        if not self._in_bounds(pe_off, 24) or self.data[pe_off : pe_off + 4] != b"PE\0\0":
            raise PEParseError("Assinatura PE invalida")

        coff = pe_off + 4
        machine_t = self._safe_unpack("<H", coff)
        nsec_t = self._safe_unpack("<H", coff + 2)
        opt_size_t = self._safe_unpack("<H", coff + 16)
        if machine_t is None or nsec_t is None or opt_size_t is None:
            raise PEParseError("COFF header truncado")
        self.machine = machine_t[0]
        num_sections = nsec_t[0]
        opt_size = opt_size_t[0]

        opt = coff + 20
        magic_t = self._safe_unpack("<H", opt)
        if magic_t is None:
            raise PEParseError("Optional header truncado")
        magic = magic_t[0]
        if magic != 0x20B:
            raise PEParseError(f"Apenas PE32+ suportado (magic={magic:#x})")

        base_t = self._safe_unpack("<Q", opt + 24)
        entry_t = self._safe_unpack("<I", opt + 16)
        if base_t is None or entry_t is None:
            raise PEParseError("Optional header truncado (base/entry)")
        self.image_base = base_t[0]
        self.entry_rva = entry_t[0]

        data_dirs_off = opt + 112
        exp = self._safe_unpack("<II", data_dirs_off)
        imp = self._safe_unpack("<II", data_dirs_off + 8)
        dly = self._safe_unpack("<II", data_dirs_off + 40)
        if exp is None or imp is None or dly is None:
            raise PEParseError("Data directories truncados")
        self.export_rva, self.export_size = exp
        self.import_rva, self.import_size = imp
        self.delay_rva, self.delay_size = dly

        sec_off = opt + opt_size
        self.sections: list[Section] = []
        for i in range(num_sections):
            s = sec_off + i * 40
            if not self._in_bounds(s, 40):
                break
            name = self.data[s : s + 8].rstrip(b"\0").decode("ascii", "ignore")
            hdr = self._safe_unpack("<IIII", s + 8)
            if hdr is None:
                break
            vsize, vaddr, rawsize, rawoff = hdr
            self.sections.append(Section(name, vaddr, vsize, rawsize, rawoff))

    def rva_to_offset(self, rva: int) -> int | None:
        for sec in self.sections:
            if sec.virtual_address <= rva < sec.virtual_address + max(sec.raw_size, sec.virtual_size):
                off = sec.raw_offset + (rva - sec.virtual_address)
                if self._in_bounds(off, 1):
                    return off
                return None
        return None

    def offset_to_rva(self, off: int) -> int | None:
        for sec in self.sections:
            if sec.raw_offset <= off < sec.raw_offset + sec.raw_size:
                return sec.virtual_address + (off - sec.raw_offset)
        return None

    def va_to_offset(self, va: int) -> int | None:
        return self.rva_to_offset(va - self.image_base)

    def read_cstring_rva(self, rva: int, max_len: int = 512) -> str:
        off = self.rva_to_offset(rva)
        if off is None:
            return ""
        end_search = min(off + max_len, len(self.data))
        idx = self.data.find(b"\0", off, end_search)
        if idx < 0:
            return ""
        return self.data[off:idx].decode("ascii", "ignore")

    def export_names(self) -> list[str]:
        if not self.export_rva:
            return []
        exp_off = self.rva_to_offset(self.export_rva)
        if exp_off is None:
            return []

        hdr = self._safe_unpack("<III", exp_off + 24)  # num_names, addr_of_funcs, addr_of_names
        if hdr is None:
            return []
        num_names = hdr[0]
        if num_names <= 0 or num_names > 200000:
            return []
        names_t = self._safe_unpack("<I", exp_off + 32)
        ords_t = self._safe_unpack("<I", exp_off + 36)
        if names_t is None or ords_t is None:
            return []
        names_rva = names_t[0]
        ords_rva = ords_t[0]

        names_off = self.rva_to_offset(names_rva)
        ords_off = self.rva_to_offset(ords_rva)
        if names_off is None or ords_off is None:
            return []

        out: list[str] = []
        for i in range(num_names):
            entry = self._safe_unpack("<I", names_off + i * 4)
            if entry is None:
                break
            name = self.read_cstring_rva(entry[0])
            if name:
                out.append(name)
        return sorted(out)

    def delay_imports(self) -> list[DelayImportModule]:
        if not self.delay_rva:
            return []

        off = self.rva_to_offset(self.delay_rva)
        if off is None:
            return []

        # Limita percurso pelo tamanho da diretoria (se declarado)
        end_off = len(self.data)
        if self.delay_size:
            declared_end = off + self.delay_size
            if declared_end <= len(self.data):
                end_off = declared_end

        modules: list[DelayImportModule] = []
        max_modules = 512
        while len(modules) < max_modules and off + 32 <= end_off:
            entry = self._safe_unpack("<IIIIIIII", off)
            if entry is None:
                break
            attrs, name_rva, _, iat_rva, int_rva, _, _, _ = entry
            if attrs == 0 and name_rva == 0:
                break

            dll_name = self.read_cstring_rva(name_rva) if name_rva else ""
            funcs: list[DelayImportFunc] = []
            idx = 0
            int_off = self.rva_to_offset(int_rva) if int_rva else None
            if int_off is not None:
                pos = int_off
                max_funcs = 8192
                while idx < max_funcs:
                    ent = self._safe_unpack("<Q", pos)
                    if ent is None:
                        break
                    ent_val = ent[0]
                    if ent_val == 0:
                        break
                    # Ignora ordinal-only (bit alto setado)
                    if not (ent_val & 0x8000000000000000):
                        hint_name_off = self.rva_to_offset(ent_val)
                        if hint_name_off is not None and self._in_bounds(hint_name_off + 2, 1):
                            end_scan = min(hint_name_off + 2 + 256, len(self.data))
                            nul = self.data.find(b"\0", hint_name_off + 2, end_scan)
                            if nul > 0:
                                fn = self.data[hint_name_off + 2 : nul].decode("ascii", "ignore")
                                if fn:
                                    funcs.append(DelayImportFunc(fn, iat_rva + idx * 8, idx))
                    idx += 1
                    pos += 8

            modules.append(DelayImportModule(dll_name, funcs))
            off += 32
        return modules

    def find_delay_import_module(self, dll_substring: str) -> DelayImportModule | None:
        needle = dll_substring.lower()
        for mod in self.delay_imports():
            if needle in mod.dll_name.lower():
                return mod
        return None

    def executable_sections(self) -> Iterator[Section]:
        for sec in self.sections:
            if sec.raw_size > 0 and sec.name.rstrip("\0") in {".text", "CODE", ".text$mn"}:
                yield sec
            elif sec.raw_size > 0 and ".text" in sec.name:
                yield sec

    def scan_lea_iat_stubs(self, iat_rvas: set[int]) -> dict[int, str]:
        """Encontra stubs delay-load: LEA RAX,[RIP+disp] ; JMP helper."""
        hits: dict[int, str] = {}
        targets = {self.image_base + rva for rva in iat_rvas}

        for sec in self.sections:
            if sec.raw_size == 0:
                continue
            end_off = min(sec.raw_offset + sec.raw_size, len(self.data))
            chunk = self.data[sec.raw_offset : end_off]
            sec_va = self.image_base + sec.virtual_address

            i = 0
            while i + 12 <= len(chunk):
                if chunk[i] == 0x48 and chunk[i + 1] == 0x8D and chunk[i + 2] in (0x05, 0x0D):
                    disp = struct.unpack_from("<i", chunk, i + 3)[0]
                    rip = sec_va + i + 7
                    target = rip + disp
                    if target in targets and chunk[i + 7 : i + 9] == b"\x48\xFF":
                        file_off = sec.raw_offset + i
                        hits[file_off] = hex(target)
                i += 1
        return hits

    def build_mov_eax_ret_patch(self, value: int) -> bytes:
        return bytes([0xB8, value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF, 0xC3, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90])

    def is_already_patched(self, offset: int) -> bool:
        if not self._in_bounds(offset, 6):
            return False
        return self.data[offset] == 0xB8 and self.data[offset + 5] == 0xC3

    def patch_bytes(self, offset: int, patch: bytes) -> None:
        if not self._in_bounds(offset, len(patch)):
            raise PEParseError(f"Patch fora do arquivo: off=0x{offset:X} size={len(patch)}")
        data = bytearray(self.data)
        data[offset : offset + len(patch)] = patch
        self.data = bytes(data)

    def save(self, path: str | Path | None = None) -> Path:
        out = Path(path) if path else self.path
        out.write_bytes(self.data)
        return out
