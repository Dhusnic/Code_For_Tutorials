from __future__ import annotations

import argparse
import csv
import io
import re
import struct
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import msoffcrypto
import pypdf
import yaml


FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
DEFAULT_DATE_OUTPUT_FORMAT = "%d/%m/%Y"
INPUT_DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y")
HEADER_KEYS = {
    "DATE": "date",
    "NARRATION": "narration",
    "CHQREFNO": "reference",
    "VALUEDT": "value_date",
    "WITHDRAWALAMT": "withdrawal",
    "DEPOSITAMT": "deposit",
    "CLOSINGBALANCE": "closing_balance",
}
EXPECTED_HEADER_ORDER = (
    "date",
    "narration",
    "reference",
    "value_date",
    "withdrawal",
    "deposit",
    "closing_balance",
)
ISO_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


@dataclass
class SheetCells:
    name: str
    cells: dict[tuple[int, int], Any]


@dataclass
class NarrationDetails:
    kind: str = ""
    payee: str = ""
    note: str = ""
    vpa: str = ""
    bank_code: str = ""
    parsed_reference: str = ""
    source_hint: str = ""


@dataclass
class Transaction:
    statement_path: Path
    statement_kind: str
    account_number: str
    account_name: str
    branch: str
    statement_from: date | None
    statement_to: date | None
    date: date
    value_date: date | None
    narration: str
    reference: str
    amount: Decimal
    direction: str
    closing_balance: Decimal | None
    row_number: int
    holder_name: str = ""
    source_id: str = ""
    account_id: str = ""


@dataclass
class Statement:
    path: Path
    sheet_name: str
    statement_kind: str
    account_number: str
    account_name: str
    branch: str
    holder_name: str
    statement_from: date | None
    statement_to: date | None
    transactions: list[Transaction] = field(default_factory=list)
    source_id: str = ""
    account_id: str = ""


@dataclass
class MoneyManagerRecord:
    sort_date: date
    date_text: str
    source_account: str
    category: str
    subcategory: str
    note: str
    amount: Decimal
    transaction_type: str
    description: str
    sub_amount: str = ""
    sub_currency: str = ""
    counterpart_account: str = ""
    currency: str = "INR"


@dataclass
class TransferCandidate:
    transaction_key: str
    statement_key: str
    transaction: Transaction
    details: NarrationDetails
    amount: Decimal
    direction: str
    source_account_id: str
    normalized_ids: tuple[str, ...] = ()
    counterpart_account_id: str = ""
    own_account_signal: bool = False


@dataclass
class TransferMatchPlan:
    suppressed_transaction_keys: set[str] = field(default_factory=set)
    synthetic_records_by_statement: dict[str, list[MoneyManagerRecord]] = field(default_factory=dict)
    candidate_counts_by_statement: dict[str, int] = field(default_factory=dict)
    synthetic_counts_by_statement: dict[str, int] = field(default_factory=dict)
    suppressed_counts_by_statement: dict[str, int] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)


@dataclass
class OutputTemplate:
    headers: list[str]
    sheet_name: str
    template_mode: str


@dataclass
class HistoricalReference:
    source_path: Path | None = None
    accounts: list[str] = field(default_factory=list)
    token_mappings: dict[str, Counter[tuple[str, str, str]]] = field(default_factory=dict)
    stopwords: set[str] = field(default_factory=set)
    min_score: int = 2


class ConversionError(Exception):
    pass


class CFBFile:
    def __init__(self, data: bytes) -> None:
        if data[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ConversionError("Not a legacy Excel/CFB workbook.")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
        self.mini_sector_size = 1 << struct.unpack_from("<H", data, 32)[0]
        self.num_fat_sectors = struct.unpack_from("<I", data, 44)[0]
        self.first_dir_sector = struct.unpack_from("<I", data, 48)[0]
        self.mini_stream_cutoff = struct.unpack_from("<I", data, 56)[0]
        self.first_minifat_sector = struct.unpack_from("<I", data, 60)[0]
        self.num_minifat_sectors = struct.unpack_from("<I", data, 64)[0]
        self.first_difat_sector = struct.unpack_from("<I", data, 68)[0]
        self.num_difat_sectors = struct.unpack_from("<I", data, 72)[0]
        self.difat = list(struct.unpack_from("<109I", data, 76))
        self.fat = self._load_fat()
        self.directories = self._load_directories()
        self.root = self.directories[0]
        self.root_stream = (
            self._read_fat_stream(self.root["start"], self.root["size"])
            if self.root["start"] != ENDOFCHAIN
            else b""
        )
        self.minifat = self._load_minifat()

    def _sector_bytes(self, sector_id: int) -> bytes:
        offset = 512 + (sector_id * self.sector_size)
        return self.data[offset : offset + self.sector_size]

    def _load_fat(self) -> list[int]:
        difat = [sector for sector in self.difat if sector != FREESECT]
        sector_id = self.first_difat_sector
        for _ in range(self.num_difat_sectors):
            if sector_id == ENDOFCHAIN:
                break
            sector = self._sector_bytes(sector_id)
            entries = struct.unpack("<%dI" % (self.sector_size // 4), sector)
            difat.extend(entries[:-1])
            sector_id = entries[-1]

        fat: list[int] = []
        for sector_id in difat[: self.num_fat_sectors]:
            fat.extend(struct.unpack("<%dI" % (self.sector_size // 4), self._sector_bytes(sector_id)))
        return fat

    def _load_directories(self) -> list[dict[str, Any]]:
        directory_data = self._read_fat_stream(self.first_dir_sector)
        directories: list[dict[str, Any]] = []
        for offset in range(0, len(directory_data), 128):
            entry = directory_data[offset : offset + 128]
            if len(entry) < 128:
                break
            name_length = struct.unpack_from("<H", entry, 64)[0]
            name = (
                entry[: max(0, name_length - 2)].decode("utf-16le", errors="ignore")
                if name_length >= 2
                else ""
            )
            directories.append(
                {
                    "name": name,
                    "type": entry[66],
                    "start": struct.unpack_from("<I", entry, 116)[0],
                    "size": struct.unpack_from("<Q", entry, 120)[0],
                }
            )
        return directories

    def _load_minifat(self) -> list[int]:
        if self.first_minifat_sector in (ENDOFCHAIN, FREESECT) or self.num_minifat_sectors == 0:
            return []
        raw = self._read_fat_stream(self.first_minifat_sector, self.num_minifat_sectors * self.sector_size)
        return list(struct.unpack("<%dI" % (len(raw) // 4), raw))

    def _follow_chain(self, start_sector: int, fat: list[int] | None = None) -> list[int]:
        active_fat = fat if fat is not None else self.fat
        chain: list[int] = []
        seen: set[int] = set()
        sector_id = start_sector
        while sector_id not in (ENDOFCHAIN, FREESECT) and sector_id < len(active_fat):
            if sector_id in seen:
                raise ConversionError("Detected a sector loop while reading workbook.")
            seen.add(sector_id)
            chain.append(sector_id)
            sector_id = active_fat[sector_id]
        return chain

    def _read_fat_stream(self, start_sector: int, size: int | None = None) -> bytes:
        data = b"".join(self._sector_bytes(sector_id) for sector_id in self._follow_chain(start_sector))
        return data if size is None else data[:size]

    def read_stream(self, stream_name: str) -> bytes:
        entry = next((item for item in self.directories if item["name"] == stream_name), None)
        if entry is None:
            raise ConversionError(f"Workbook stream '{stream_name}' was not found.")
        if entry["size"] < self.mini_stream_cutoff and entry["type"] == 2:
            chunks: list[bytes] = []
            for sector_id in self._follow_chain(entry["start"], self.minifat):
                offset = sector_id * self.mini_sector_size
                chunks.append(self.root_stream[offset : offset + self.mini_sector_size])
            return b"".join(chunks)[: entry["size"]]
        return self._read_fat_stream(entry["start"], entry["size"])


class ContinuedRecordReader:
    def __init__(self, fragments: list[bytes]) -> None:
        self.fragments = fragments
        self.fragment_index = 0
        self.offset = 0

    def _advance(self) -> None:
        self.fragment_index += 1
        self.offset = 0
        if self.fragment_index >= len(self.fragments):
            raise ConversionError("Unexpected end of SST fragments.")

    def read(self, size: int) -> bytes:
        output = bytearray()
        remaining = size
        while remaining > 0:
            fragment = self.fragments[self.fragment_index]
            available = len(fragment) - self.offset
            if available <= 0:
                self._advance()
                continue
            take = min(remaining, available)
            output.extend(fragment[self.offset : self.offset + take])
            self.offset += take
            remaining -= take
        return bytes(output)

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_u16(self) -> int:
        return struct.unpack("<H", self.read(2))[0]

    def read_u32(self) -> int:
        return struct.unpack("<I", self.read(4))[0]

    def read_chars(self, count: int, is_16_bit: bool) -> str:
        pieces: list[str] = []
        remaining = count
        while remaining > 0:
            fragment = self.fragments[self.fragment_index]
            available = len(fragment) - self.offset
            if available <= 0:
                self._advance()
                is_16_bit = bool(self.read_u8() & 0x01)
                fragment = self.fragments[self.fragment_index]
                available = len(fragment) - self.offset

            char_width = 2 if is_16_bit else 1
            take = min(remaining, available // char_width)
            if take == 0:
                self._advance()
                is_16_bit = bool(self.read_u8() & 0x01)
                continue
            encoding = "utf-16le" if is_16_bit else "latin1"
            pieces.append(self.read(take * char_width).decode(encoding, errors="ignore"))
            remaining -= take
        return "".join(pieces)


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = dict(base)
        for key, value in override.items():
            merged[key] = deep_merge(base.get(key), value) if key in base else value
        return merged
    return override if override is not None else base


def default_config() -> dict[str, Any]:
    return {
        "input": {
            "directory": "inputs",
            "patterns": ["*.xls", "*.xlsx", "*.pdf"],
            "recursive": False,
        },
        "output": {
            "directory": "outputs",
            "combine_statements": True,
            "write_individual_files": True,
            "write_tsv": True,
            "write_xlsx": True,
            "template_mode": "auto",
            "template_sample": "",
            "combined_file_name": "money_manager_import_all_accounts",
            "date_format": DEFAULT_DATE_OUTPUT_FORMAT,
        },
        "money_manager": {
            "default_currency": "INR",
            "default_expense_category": "General Expense",
            "default_expense_subcategory": "",
            "default_income_category": "General Income",
            "default_income_subcategory": "",
            "transfer_in_strategy": "income",
            "transfer_in_category": "Transfer In",
            "transfer_in_subcategory": "",
            "note_include_raw_narration": True,
            "note_include_bank_reference": True,
            "note_include_vpa": True,
            "fallback_account_prefix": "HDFC",
        },
        "history": {
            "enabled": True,
            "reference_export": "",
            "min_score": 2,
            "stopwords": [
                "FOR",
                "THE",
                "AND",
                "TO",
                "MY",
                "ME",
                "WITH",
                "FROM",
                "MONTH",
                "GIVEN",
                "GIVE",
                "THIS",
                "THAT",
                "PAYMENT",
                "PAY",
                "UPI",
                "CARD",
                "RAW",
                "HDFC",
                "ACCOUNT",
                "TRANSFER",
            ],
            "account_name_hints": {
                "bank_account_keywords": ["SALARY"],
                "credit_card_keywords": ["CARD"],
                "savings_account_keywords": ["SAVINGS"],
            },
        },
        "statement_types": {
            "credit_card": {
                "skip_payment_credits": True,
                "payment_credit_keywords": ["CC PAYMENT", "PAYZAPP"],
            }
        },
        "statement_sources": {
            "hdfc_acc": {
                "parser": "hdfc_bank",
                "account_id": "hdfc_salary_account",
                "file_match": {
                    "filename_contains": ["hdfc_acc", "hdfc_account", "acct_statement"],
                    "extensions": [".xls", ".xlsx", ".pdf"],
                },
            },
            "hdfc_credit_card": {
                "parser": "hdfc_credit_card",
                "account_id": "hdfc_credit_card",
                "file_match": {
                    "filename_contains": ["hdfc_credit_card", "credit_card"],
                    "extensions": [".xls", ".xlsx", ".pdf"],
                },
            },
            "sbi_acc": {
                "parser": "sbi_bank",
                "account_id": "sbi_salary_account",
                "file_match": {
                    "filename_contains": ["sbi_acc", "sbi_account", "sbi_statement"],
                    "extensions": [".xls", ".xlsx", ".pdf"],
                },
            },
            "ippnb_acc": {
                "parser": "ippb_bank",
                "account_id": "ippnb_account",
                "file_match": {
                    "filename_contains": ["ippnb_acc", "ippnb_account", "ippb_statement", "ippb_acc"],
                    "extensions": [".xls", ".xlsx", ".pdf"],
                },
            },
        },
        "identity": {
            "names": [],
            "vpas": [],
            "keywords": ["SELF TRANSFER"],
        },
        "accounts": {},
        "transfer_targets": [],
        "rules": [],
    }


def load_config(path: Path) -> dict[str, Any]:
    user_config = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            if not isinstance(loaded, dict):
                raise ConversionError("config.yml must contain a YAML object at the top level.")
            user_config = loaded
    return deep_merge(default_config(), user_config)


def password_for_source(config: dict[str, Any], source_id: str) -> str:
    if not source_id:
        return ""
    source_config = (config.get("statement_sources", {}) or {}).get(source_id, {}) or {}
    return str(source_config.get("password", "") or "")


def iter_accounts(config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    accounts = config.get("accounts", {}) or {}
    return [(account_id, account_config or {}) for account_id, account_config in accounts.items()]


def get_account_by_id(config: dict[str, Any], account_id: str) -> dict[str, Any]:
    return (config.get("accounts", {}) or {}).get(account_id, {}) or {}


def resolve_account_id(
    config: dict[str, Any],
    *,
    account_number: str = "",
    source_id: str = "",
    explicit_account_id: str = "",
) -> str:
    if explicit_account_id and explicit_account_id in (config.get("accounts", {}) or {}):
        return explicit_account_id

    if source_id:
        source_config = (config.get("statement_sources", {}) or {}).get(source_id, {}) or {}
        source_account_id = normalize_text(source_config.get("account_id", ""))
        if source_account_id and source_account_id in (config.get("accounts", {}) or {}):
            return source_account_id

    normalized_number = normalize_text(account_number)
    if normalized_number:
        for account_id, account_config in iter_accounts(config):
            numbers = [normalize_text(item) for item in (account_config.get("account_numbers", []) or [])]
            if normalized_number in numbers:
                return account_id
        if normalized_number in (config.get("accounts", {}) or {}):
            return normalized_number
    return ""


def resolve_account_reference(config: dict[str, Any], rule: dict[str, Any]) -> str:
    account_name = normalize_text(rule.get("account", ""))
    if account_name:
        return account_name
    account_id = normalize_text(rule.get("account_id", ""))
    if account_id:
        account_config = get_account_by_id(config, account_id)
        resolved = normalize_text(account_config.get("money_manager_name", ""))
        if resolved:
            return resolved
    counterpart_name = normalize_text(rule.get("counterpart_account", ""))
    if counterpart_name:
        return counterpart_name
    counterpart_id = normalize_text(rule.get("counterpart_account_id", ""))
    if counterpart_id:
        account_config = get_account_by_id(config, counterpart_id)
        resolved = normalize_text(account_config.get("money_manager_name", ""))
        if resolved:
            return resolved
    return ""


def resolve_account_reference_id(config: dict[str, Any], rule: dict[str, Any]) -> str:
    accounts = config.get("accounts", {}) or {}

    for key in ("account_id", "counterpart_account_id"):
        account_id = normalize_text(rule.get(key, ""))
        if account_id and account_id in accounts:
            return account_id

    reference_name = normalize_text(rule.get("account", "")) or normalize_text(rule.get("counterpart_account", ""))
    if not reference_name:
        return ""
    for account_id, account_config in iter_accounts(config):
        configured_name = normalize_text(account_config.get("money_manager_name", ""))
        if configured_name and configured_name == reference_name:
            return account_id
    return ""


def source_matches_path(source_config: dict[str, Any], path: Path) -> bool:
    match_config = source_config.get("file_match", {}) or {}
    extensions = [normalize_text(item).lower() for item in (match_config.get("extensions", []) or []) if normalize_text(item)]
    if extensions and path.suffix.lower() not in extensions:
        return False
    contains_values = [normalize_text(item).lower() for item in (match_config.get("filename_contains", []) or []) if normalize_text(item)]
    if contains_values:
        lowered_name = path.name.lower()
        return any(item in lowered_name for item in contains_values)
    return False


def candidate_source_ids(config: dict[str, Any], path: Path) -> list[str]:
    sources = config.get("statement_sources", {}) or {}
    return [source_id for source_id, source_config in sources.items() if source_matches_path(source_config, path)]


def bind_statement_identity(config: dict[str, Any], statement: Statement, source_id: str = "", account_id: str = "") -> Statement:
    resolved_account_id = resolve_account_id(
        config,
        account_number=statement.account_number,
        source_id=source_id,
        explicit_account_id=account_id,
    )
    statement.source_id = source_id
    statement.account_id = resolved_account_id
    for transaction in statement.transactions:
        transaction.source_id = source_id
        transaction.account_id = resolved_account_id
    return statement


def statement_key(statement: Statement) -> str:
    return f"{statement.path.resolve()}::{statement.sheet_name}"


def transaction_key(transaction: Transaction) -> str:
    return f"{transaction.statement_path.resolve()}::{transaction.row_number}"


def normalize_label(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("\n", " ")).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def normalize_transaction_token(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()
    if cleaned.isdigit():
        return cleaned.lstrip("0") or "0"
    return cleaned


def normalize_money_manager_type(value: str | None) -> str:
    cleaned = normalize_text(value or "").lower()
    if cleaned in {"income", "in"}:
        return "Income"
    if cleaned in {"expense", "expenses", "debit", "out"}:
        return "Expense"
    if cleaned in {"transfer-out", "transfer out", "transfer"}:
        return "Transfer-Out"
    return ""


def title_from_masked_account(account_number: str, prefix: str) -> str:
    digits = re.sub(r"\D+", "", account_number or "")
    if not digits:
        return prefix
    return f"{prefix} {digits[-4:]}"


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_text(value)
    if not text:
        return None
    for fmt in INPUT_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_card_statement_datetime(value: Any) -> tuple[date | None, str]:
    text = normalize_text(value)
    if not text:
        return None, ""
    for fmt in ("%d/%m/%Y / %H:%M", "%d/%m/%Y/%H:%M", "%d/%m/%Y %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date(), parsed.strftime("%H:%M")
        except ValueError:
            continue
    if " / " in text:
        left, right = text.split(" / ", 1)
        return parse_date(left), normalize_text(right)
    return parse_date(text), ""


def format_upi_note(note_text: str, parsed_reference: str) -> str:
    message = normalize_text(note_text)
    if message.upper() == "UPI":
        message = ""
    if parsed_reference:
        return f"{message} ({parsed_reference})" if message else f"({parsed_reference})"
    return message


def format_date(value: date | None, output_format: str) -> str:
    return value.strftime(output_format) if value else ""


def decimal_from_number(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = normalize_text(value).replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def format_amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def read_excel_bytes(path: Path, password: str = "") -> bytes:
    try:
        raw = path.read_bytes()
    except PermissionError as exc:
        raise ConversionError(f"{path.name} is open or locked by another application and could not be read.") from exc

    try:
        office = msoffcrypto.OfficeFile(io.BytesIO(raw))
        if not office.is_encrypted():
            return raw
        if not password:
            raise ConversionError(f"{path.name} is password-protected but no password is configured in config.yml.")
        office.load_key(password=password)
        decrypted = io.BytesIO()
        office.decrypt(decrypted)
        return decrypted.getvalue()
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Could not open password-protected Excel file {path.name}: {exc}") from exc


def read_pdf_text(path: Path, password: str = "") -> str:
    try:
        with path.open("rb") as handle:
            reader = pypdf.PdfReader(handle)
            if reader.is_encrypted:
                if not password:
                    raise ConversionError(f"{path.name} is password-protected but no password is configured in config.yml.")
                decrypt_result = reader.decrypt(password)
                if decrypt_result == 0:
                    raise ConversionError(f"The configured password for {path.name} is not valid.")
            texts = []
            for page in reader.pages:
                texts.append(page.extract_text() or "")
            return "\n".join(texts)
    except PermissionError as exc:
        raise ConversionError(f"{path.name} is open or locked by another application and could not be read.") from exc
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"Could not read PDF file {path.name}: {exc}") from exc


def read_short_unicode(data: bytes, offset: int) -> tuple[str, int]:
    character_count = data[offset]
    flags = data[offset + 1]
    offset += 2
    rich_text_runs = struct.unpack_from("<H", data, offset)[0] if flags & 0x08 else 0
    offset += 2 if flags & 0x08 else 0
    extension_size = struct.unpack_from("<I", data, offset)[0] if flags & 0x04 else 0
    offset += 4 if flags & 0x04 else 0
    if flags & 0x01:
        text = data[offset : offset + (character_count * 2)].decode("utf-16le", errors="ignore")
        offset += character_count * 2
    else:
        text = data[offset : offset + character_count].decode("latin1", errors="ignore")
        offset += character_count
    offset += (rich_text_runs * 4) + extension_size
    return text, offset


def decode_rk(raw_value: int) -> Decimal:
    multiply_by_100 = raw_value & 0x01
    is_integer = raw_value & 0x02
    if is_integer:
        value = Decimal(raw_value >> 2)
    else:
        packed = struct.pack("<Q", (raw_value & 0xFFFFFFFC) << 32)
        value = Decimal(str(struct.unpack("<d", packed)[0]))
    if multiply_by_100:
        value = value / Decimal("100")
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_sst(workbook_stream: bytes, start_offset: int) -> tuple[list[str], int]:
    _, length = struct.unpack_from("<HH", workbook_stream, start_offset)
    fragments = [workbook_stream[start_offset + 4 : start_offset + 4 + length]]
    offset = start_offset + 4 + length
    while offset + 4 <= len(workbook_stream):
        record_id, next_length = struct.unpack_from("<HH", workbook_stream, offset)
        if record_id != 0x003C:
            break
        fragments.append(workbook_stream[offset + 4 : offset + 4 + next_length])
        offset += 4 + next_length

    unique_string_count = struct.unpack_from("<I", fragments[0], 4)[0]
    reader = ContinuedRecordReader([fragments[0][8:]] + fragments[1:])
    strings: list[str] = []
    for _ in range(unique_string_count):
        char_count = reader.read_u16()
        flags = reader.read_u8()
        rich_text_runs = reader.read_u16() if flags & 0x08 else 0
        extension_size = reader.read_u32() if flags & 0x04 else 0
        text = reader.read_chars(char_count, bool(flags & 0x01))
        if rich_text_runs:
            reader.read(rich_text_runs * 4)
        if extension_size:
            reader.read(extension_size)
        strings.append(text)
    return strings, offset


def parse_xls_sheets_bytes(data: bytes) -> list[SheetCells]:
    workbook = CFBFile(data).read_stream("Workbook")
    shared_strings: list[str] = []
    sheet_bounds: list[tuple[int, str]] = []
    offset = 0
    while offset + 4 <= len(workbook):
        record_id, length = struct.unpack_from("<HH", workbook, offset)
        record = workbook[offset + 4 : offset + 4 + length]
        if record_id == 0x0085:
            sheet_offset = struct.unpack_from("<I", record, 0)[0]
            sheet_name, _ = read_short_unicode(record, 6)
            sheet_bounds.append((sheet_offset, sheet_name))
        elif record_id == 0x00FC:
            shared_strings, offset = parse_sst(workbook, offset)
            continue
        offset += 4 + length

    sheets: list[SheetCells] = []
    for start_offset, sheet_name in sheet_bounds:
        cells: dict[tuple[int, int], Any] = {}
        offset = start_offset
        while offset + 4 <= len(workbook):
            record_id, length = struct.unpack_from("<HH", workbook, offset)
            record = workbook[offset + 4 : offset + 4 + length]
            if record_id == 0x000A:
                break
            if record_id == 0x00FD:
                row, col, _xf = struct.unpack_from("<HHH", record, 0)
                sst_index = struct.unpack_from("<I", record, 6)[0]
                cells[(row, col)] = shared_strings[sst_index]
            elif record_id == 0x0203:
                row, col, _xf = struct.unpack_from("<HHH", record, 0)
                cells[(row, col)] = decimal_from_number(struct.unpack_from("<d", record, 6)[0])
            elif record_id == 0x027E:
                row, col, _xf = struct.unpack_from("<HHH", record, 0)
                cells[(row, col)] = decode_rk(struct.unpack_from("<I", record, 6)[0])
            elif record_id == 0x00BD:
                row = struct.unpack_from("<H", record, 0)[0]
                first_col = struct.unpack_from("<H", record, 2)[0]
                last_col = struct.unpack_from("<H", record, length - 2)[0]
                cursor = 4
                col = first_col
                while col <= last_col:
                    _xf, rk_value = struct.unpack_from("<HI", record, cursor)
                    cells[(row, col)] = decode_rk(rk_value)
                    cursor += 6
                    col += 1
            elif record_id == 0x0204:
                row, col, _xf, char_count = struct.unpack_from("<HHHH", record, 0)
                cells[(row, col)] = record[8 : 8 + char_count].decode("latin1", errors="ignore")
            elif record_id == 0x00D6:
                row, col, _xf = struct.unpack_from("<HHH", record, 0)
                char_count = struct.unpack_from("<H", record, 6)[0]
                options = record[8]
                start = 9
                width = 2 if options & 0x01 else 1
                end = start + (char_count * width)
                encoding = "utf-16le" if width == 2 else "latin1"
                cells[(row, col)] = record[start:end].decode(encoding, errors="ignore")
            offset += 4 + length
        sheets.append(SheetCells(sheet_name, cells))
    return sheets


def parse_xls_sheets(path: Path) -> list[SheetCells]:
    return parse_xls_sheets_bytes(path.read_bytes())


def column_letters_to_index(letters: str) -> int:
    result = 0
    for char in letters:
        result = (result * 26) + (ord(char.upper()) - 64)
    return result - 1


def index_to_column_letters(index: int) -> str:
    current = index + 1
    chars: list[str] = []
    while current:
        current, remainder = divmod(current - 1, 26)
        chars.append(chr(65 + remainder))
    return "".join(reversed(chars))


def parse_xlsx_sheets_bytes(data: bytes) -> list[SheetCells]:
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        workbook_xml = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_xml = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {item.attrib["Id"]: item.attrib["Target"] for item in rels_xml}
        namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            sst_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for entry in sst_root:
                parts = [node.text or "" for node in entry.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                shared_strings.append("".join(parts))

        sheets: list[SheetCells] = []
        for sheet in workbook_xml.find("a:sheets", namespace) or []:
            sheet_name = sheet.attrib.get("name", "Sheet1")
            rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            if not rel_id:
                continue
            target = "xl/" + rel_map[rel_id].lstrip("/")
            sheet_xml = ET.fromstring(archive.read(target))
            cells: dict[tuple[int, int], Any] = {}
            for cell in sheet_xml.findall(".//a:sheetData/a:row/a:c", namespace):
                cell_ref = cell.attrib["r"]
                match = re.match(r"([A-Z]+)(\d+)", cell_ref)
                if not match:
                    continue
                col = column_letters_to_index(match.group(1))
                row = int(match.group(2)) - 1
                cell_type = cell.attrib.get("t", "")
                value_node = cell.find("a:v", namespace)
                inline_node = cell.find("a:is", namespace)
                if cell_type == "s" and value_node is not None:
                    cells[(row, col)] = shared_strings[int(value_node.text or "0")]
                elif cell_type == "inlineStr" and inline_node is not None:
                    texts = [node.text or "" for node in inline_node.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                    cells[(row, col)] = "".join(texts)
                elif value_node is not None:
                    raw_value = value_node.text or ""
                    if cell_type in {"str", "b"}:
                        cells[(row, col)] = raw_value
                    else:
                        cells[(row, col)] = decimal_from_number(raw_value) if re.fullmatch(r"-?\d+(\.\d+)?", raw_value) else raw_value
            sheets.append(SheetCells(sheet_name, cells))
        return sheets


def parse_xlsx_sheets(path: Path) -> list[SheetCells]:
    return parse_xlsx_sheets_bytes(path.read_bytes())


def load_sheets(path: Path, password: str = "") -> list[SheetCells]:
    suffix = path.suffix.lower()
    if suffix == ".xls":
        return parse_xls_sheets_bytes(read_excel_bytes(path, password=password))
    if suffix == ".xlsx":
        return parse_xlsx_sheets_bytes(read_excel_bytes(path, password=password))
    raise ConversionError(f"Unsupported file type: {path.name}")


def history_export_path(config: dict[str, Any], output_directory: Path) -> Path | None:
    history_config = config.get("history", {}) or {}
    configured = normalize_text(history_config.get("reference_export", ""))
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.exists():
            return candidate
    sample = normalize_text(config.get("output", {}).get("template_sample", ""))
    if sample:
        candidate = Path(sample)
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        if candidate.exists():
            return candidate
    candidates = sorted(path for path in output_directory.glob("*.xlsx") if path.is_file())
    return candidates[0] if candidates else None


def tokenize_history_text(text: str, stopwords: set[str]) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[A-Z0-9][A-Z0-9.+/&'-]{1,}", text.upper()):
        cleaned = token.strip(".-/&'+")
        if len(cleaned) < 3 or cleaned.isdigit() or cleaned in stopwords:
            continue
        tokens.append(cleaned)
    return tokens


def load_historical_reference(config: dict[str, Any], output_directory: Path) -> HistoricalReference | None:
    history_config = config.get("history", {}) or {}
    if not history_config.get("enabled", True):
        return None
    path = history_export_path(config, output_directory)
    if path is None or not path.exists():
        return None

    sheets = parse_xlsx_sheets(path)
    if not sheets:
        return None
    rows = rows_from_cells(sheets[0].cells)
    header = rows.get(0, {})
    if not header:
        return None

    columns: dict[str, int] = {}
    account_hits = 0
    for col, value in header.items():
        label = normalize_label(str(value))
        if label == "ACCOUNT" and "account" not in columns:
            columns["account"] = col
            account_hits += 1
            continue
        if label == "ACCOUNT" and "counterpart_account" not in columns:
            columns["counterpart_account"] = col
            account_hits += 1
            continue
        if label == "CATEGORY":
            columns["category"] = col
        elif label == "SUBCATEGORY":
            columns["subcategory"] = col
        elif label == "NOTE":
            columns["note"] = col
        elif label in {"INCOMEEXPENSE", "TYPE"}:
            columns["transaction_type"] = col
        elif label == "DESCRIPTION":
            columns["description"] = col

    required = {"account", "category", "subcategory", "note", "transaction_type", "description"}
    if not required.issubset(columns):
        return None

    reference = HistoricalReference(
        source_path=path,
        stopwords={normalize_text(item).upper() for item in (history_config.get("stopwords", []) or []) if normalize_text(item)},
        min_score=int(history_config.get("min_score", 2) or 2),
    )
    reference.accounts = sorted(
        {
            normalize_text(str(rows[row_index].get(columns["account"], "") or ""))
            for row_index in rows
            if row_index != 0 and normalize_text(str(rows[row_index].get(columns["account"], "") or ""))
        }
    )

    for row_index, row in rows.items():
        if row_index == 0:
            continue
        account = normalize_text(str(row.get(columns["account"], "") or ""))
        category = normalize_text(str(row.get(columns["category"], "") or ""))
        subcategory = normalize_text(str(row.get(columns["subcategory"], "") or ""))
        transaction_type = normalize_money_manager_type(str(row.get(columns["transaction_type"], "") or ""))
        note = normalize_text(str(row.get(columns["note"], "") or ""))
        description = normalize_text(str(row.get(columns["description"], "") or ""))
        if not account or not category or not transaction_type:
            continue
        token_text = " ".join(part for part in [note, description] if part)
        for token in tokenize_history_text(token_text, reference.stopwords):
            reference.token_mappings.setdefault(token, Counter())[(category, subcategory, transaction_type)] += 1
    return reference


def history_account_hint(history: HistoricalReference | None, keyword_group: list[str]) -> str:
    if history is None:
        return ""
    upper_keywords = [normalize_text(item).upper() for item in keyword_group if normalize_text(item)]
    for account in history.accounts:
        upper_account = account.upper()
        if any(keyword in upper_account for keyword in upper_keywords):
            return account
    return ""


def rows_from_cells(cells: dict[tuple[int, int], Any]) -> dict[int, dict[int, Any]]:
    rows: dict[int, dict[int, Any]] = defaultdict(dict)
    for (row, col), value in cells.items():
        rows[row][col] = value
    return dict(rows)


def find_statement_header(rows: dict[int, dict[int, Any]]) -> tuple[int, dict[str, int]]:
    for row_index in sorted(rows):
        row = rows[row_index]
        index_map: dict[str, int] = {}
        for col, value in row.items():
            key = HEADER_KEYS.get(normalize_label(value if isinstance(value, str) else str(value)))
            if key:
                index_map[key] = col
        if all(item in index_map for item in EXPECTED_HEADER_ORDER):
            return row_index, index_map
    raise ConversionError("Could not find the HDFC transaction table header.")


def extract_statement_metadata(rows: dict[int, dict[int, Any]], header_row: int) -> dict[str, str]:
    metadata: dict[str, str] = {}
    top_texts: list[str] = []
    for row_index in sorted(rows):
        if row_index >= header_row:
            break
        for col in sorted(rows[row_index]):
            value = rows[row_index][col]
            if isinstance(value, str):
                cleaned = normalize_text(value)
                if cleaned:
                    top_texts.append(cleaned)

    joined = "\n".join(top_texts)
    patterns = {
        "branch": r"Account Branch\s*:\s*(.+)",
        "account_number": r"Account No\s*:\s*([0-9X]+)",
        "statement_range": r"Statement From\s*:\s*([0-9/]+)\s*To\s*:\s*([0-9/]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, joined, re.IGNORECASE)
        if match:
            metadata[key] = " | ".join(item.strip() for item in match.groups() if item and item.strip())

    holder_name = ""
    for row_index in sorted(rows):
        if row_index >= header_row:
            break
        first_value = normalize_text(rows[row_index].get(0, ""))
        if (
            first_value
            and ":" not in first_value
            and "HDFC BANK" not in first_value.upper()
            and "STATEMENT" not in first_value.upper()
            and "*" not in first_value
        ):
            holder_name = re.sub(r"^(MR|MRS|MS|DR)\s+", "", first_value, flags=re.IGNORECASE).strip()
            break
    metadata["holder_name"] = holder_name
    return metadata


def is_star_row(row: dict[int, Any]) -> bool:
    values = [normalize_text(value) for value in row.values() if normalize_text(value)]
    return bool(values) and all(set(value) <= {"*"} for value in values)


def extract_transactions(
    rows: dict[int, dict[int, Any]],
    header_row: int,
    column_map: dict[str, int],
    statement_path: Path,
    metadata: dict[str, str],
) -> list[Transaction]:
    account_number = metadata.get("account_number", "")
    account_name = metadata.get("holder_name", "")
    branch = metadata.get("branch", "")
    start_date = None
    end_date = None
    if "statement_range" in metadata:
        parts = metadata["statement_range"].split("|")
        start_date = parse_date(parts[0].strip()) if parts else None
        end_date = parse_date(parts[1].strip()) if len(parts) > 1 else None

    transactions: list[Transaction] = []
    seen_transactions = False
    for row_index in sorted(rows):
        if row_index <= header_row:
            continue
        row = rows[row_index]
        if not row or is_star_row(row):
            continue
        row_text = " ".join(normalize_text(value) for value in row.values())
        if "STATEMENT SUMMARY" in row_text.upper() or "END OF STATEMENT" in row_text.upper():
            break

        transaction_date = parse_date(row.get(column_map["date"]))
        narration = normalize_text(row.get(column_map["narration"], ""))
        if not transaction_date or not narration:
            if seen_transactions:
                continue
            continue

        seen_transactions = True
        withdrawal = decimal_from_number(row.get(column_map["withdrawal"]))
        deposit = decimal_from_number(row.get(column_map["deposit"]))
        if withdrawal and withdrawal > Decimal("0.00"):
            direction = "debit"
            amount = withdrawal
        elif deposit and deposit > Decimal("0.00"):
            direction = "credit"
            amount = deposit
        else:
            continue

        transactions.append(
            Transaction(
                statement_path=statement_path,
                statement_kind="bank_account",
                account_number=account_number,
                account_name=account_name,
                branch=branch,
                statement_from=start_date,
                statement_to=end_date,
                date=transaction_date,
                value_date=parse_date(row.get(column_map["value_date"])),
                narration=narration,
                reference=normalize_text(row.get(column_map["reference"], "")),
                amount=amount,
                direction=direction,
                closing_balance=decimal_from_number(row.get(column_map["closing_balance"])),
                row_number=row_index + 1,
                holder_name=account_name,
            )
        )
    return transactions


def parse_bank_statement_from_sheet(path: Path, sheet: SheetCells) -> Statement:
    rows = rows_from_cells(sheet.cells)
    header_row, column_map = find_statement_header(rows)
    metadata = extract_statement_metadata(rows, header_row)
    transactions = extract_transactions(rows, header_row, column_map, path, metadata)
    if not transactions:
        raise ConversionError(f"No transactions found in {path.name} ({sheet.name}).")
    start_date = transactions[0].statement_from or min(item.date for item in transactions)
    end_date = transactions[0].statement_to or max(item.date for item in transactions)
    return Statement(
        path=path,
        sheet_name=sheet.name,
        statement_kind="bank_account",
        account_number=metadata.get("account_number", ""),
        account_name=metadata.get("holder_name", ""),
        branch=metadata.get("branch", ""),
        holder_name=metadata.get("holder_name", ""),
        statement_from=start_date,
        statement_to=end_date,
        transactions=transactions,
    )


def find_sbi_statement_header(rows: dict[int, dict[int, Any]]) -> tuple[int, dict[str, int]]:
    header_map = {
        "DATE": "date",
        "DETAILS": "narration",
        "REFNOCHEQUENO": "reference",
        "DEBIT": "withdrawal",
        "CREDIT": "deposit",
        "BALANCE": "closing_balance",
    }
    for row_index in sorted(rows):
        row = rows[row_index]
        index_map: dict[str, int] = {}
        for col, value in row.items():
            key = header_map.get(normalize_label(str(value)))
            if key:
                index_map[key] = col
        if {"date", "narration", "withdrawal", "deposit", "closing_balance"}.issubset(index_map):
            return row_index, index_map
    raise ConversionError("Could not find the SBI transaction table header.")


def extract_sbi_statement_metadata(rows: dict[int, dict[int, Any]], header_row: int) -> dict[str, str]:
    metadata: dict[str, str] = {}
    top_texts: list[str] = []
    for row_index in sorted(rows):
        if row_index >= header_row:
            break
        for col in sorted(rows[row_index]):
            value = rows[row_index][col]
            if isinstance(value, str):
                cleaned = normalize_text(value)
                if cleaned:
                    top_texts.append(cleaned)

    joined = "\n".join(top_texts)
    patterns = {
        "branch": r"Branch Name\s*:\s*(.+)",
        "account_number": r"Account Number\s*:\s*([0-9X]+)",
        "statement_range": r"Statement From\s*:\s*([0-9/-]+)\s*to\s*([0-9/-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, joined, re.IGNORECASE)
        if match:
            metadata[key] = " | ".join(item.strip() for item in match.groups() if item and item.strip())

    holder_name = ""
    first_cell = normalize_text(rows.get(1, {}).get(0, ""))
    if first_cell:
        holder_name = normalize_text(first_cell.split("@", 1)[0])
    metadata["holder_name"] = holder_name
    return metadata


def extract_sbi_bank_reference(narration: str) -> str:
    match = re.search(r"\b([0-9]{10,})\s+AT\s+[0-9A-Z]+\b", normalize_text(narration), re.IGNORECASE)
    return match.group(1) if match else ""


def extract_sbi_transactions(
    rows: dict[int, dict[int, Any]],
    header_row: int,
    column_map: dict[str, int],
    statement_path: Path,
    metadata: dict[str, str],
) -> list[Transaction]:
    account_number = metadata.get("account_number", "")
    account_name = metadata.get("holder_name", "")
    branch = metadata.get("branch", "")
    start_date = None
    end_date = None
    if "statement_range" in metadata:
        parts = metadata["statement_range"].split("|")
        start_date = parse_date(parts[0].strip()) if parts else None
        end_date = parse_date(parts[1].strip()) if len(parts) > 1 else None

    transactions: list[Transaction] = []
    for row_index in sorted(rows):
        if row_index <= header_row:
            continue
        row = rows[row_index]
        if not row:
            continue
        row_text = " ".join(normalize_text(value) for value in row.values())
        if "STATEMENT SUMMARY" in row_text.upper():
            break

        transaction_date = parse_date(row.get(column_map["date"]))
        narration = normalize_text(row.get(column_map["narration"], ""))
        if not transaction_date or not narration:
            continue

        withdrawal = decimal_from_number(row.get(column_map["withdrawal"]))
        deposit = decimal_from_number(row.get(column_map["deposit"]))
        if withdrawal and withdrawal > Decimal("0.00"):
            direction = "debit"
            amount = withdrawal
        elif deposit and deposit > Decimal("0.00"):
            direction = "credit"
            amount = deposit
        else:
            continue

        reference = normalize_text(row.get(column_map.get("reference", -1), ""))
        if not reference:
            reference = extract_sbi_bank_reference(narration)

        transactions.append(
            Transaction(
                statement_path=statement_path,
                statement_kind="bank_account",
                account_number=account_number,
                account_name=account_name,
                branch=branch,
                statement_from=start_date,
                statement_to=end_date,
                date=transaction_date,
                value_date=transaction_date,
                narration=narration,
                reference=reference,
                amount=amount,
                direction=direction,
                closing_balance=decimal_from_number(row.get(column_map["closing_balance"])),
                row_number=row_index + 1,
                holder_name=account_name,
            )
        )
    return transactions


def parse_sbi_statement_from_sheet(path: Path, sheet: SheetCells) -> Statement:
    rows = rows_from_cells(sheet.cells)
    header_row, column_map = find_sbi_statement_header(rows)
    metadata = extract_sbi_statement_metadata(rows, header_row)
    transactions = extract_sbi_transactions(rows, header_row, column_map, path, metadata)
    if not transactions:
        raise ConversionError(f"No SBI transactions found in {path.name} ({sheet.name}).")
    start_date = transactions[0].statement_from or min(item.date for item in transactions)
    end_date = transactions[0].statement_to or max(item.date for item in transactions)
    return Statement(
        path=path,
        sheet_name=sheet.name,
        statement_kind="bank_account",
        account_number=metadata.get("account_number", ""),
        account_name=metadata.get("holder_name", ""),
        branch=metadata.get("branch", ""),
        holder_name=metadata.get("holder_name", ""),
        statement_from=start_date,
        statement_to=end_date,
        transactions=transactions,
    )


def find_credit_card_header(rows: dict[int, dict[int, Any]]) -> tuple[int, dict[str, int]]:
    header_map = {
        "TRANSACTIONTYPE": "transaction_type",
        "PRIMARYADDONCUSTOMERNAME": "customer_name",
        "DATETIME": "date_time",
        "DESCRIPTION": "description",
        "AMT": "amount",
        "DEBITCREDIT": "debit_credit",
    }
    for row_index in sorted(rows):
        row = rows[row_index]
        index_map: dict[str, int] = {}
        for col, value in row.items():
            key = header_map.get(normalize_label(str(value)))
            if key:
                index_map[key] = col
        if {"date_time", "description", "amount", "debit_credit"}.issubset(index_map):
            return row_index, index_map
    raise ConversionError("Could not find the HDFC credit-card transaction table header.")


def extract_credit_card_metadata(rows: dict[int, dict[int, Any]], header_row: int) -> dict[str, str]:
    texts: list[str] = []
    for row_index in sorted(rows):
        if row_index >= header_row:
            break
        for col in sorted(rows[row_index]):
            value = normalize_text(rows[row_index][col])
            if value:
                texts.append(value)
    joined = "\n".join(texts)
    metadata: dict[str, str] = {}
    patterns = {
        "card_number": r"Credit Card No\.\s*:\s*([0-9X]+)",
        "statement_date": r"Statement Date\s*([0-9]{1,2}\s+[A-Za-z]+,\s+[0-9]{4})",
        "payment_due_date": r"Payment Due Date\s*([0-9]{1,2}\s+[A-Za-z]+,\s+[0-9]{4})",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, joined, re.IGNORECASE)
        if match:
            metadata[key] = normalize_text(match.group(1))

    holder_name = ""
    for row_index in sorted(rows):
        if row_index >= header_row:
            break
        row = rows[row_index]
        for col in sorted(row):
            value = normalize_text(row[col])
            if value and value not in {"Name", "Address", "Customer GSTN"} and ":" not in value:
                holder_name = value
                break
        if holder_name:
            break
    metadata["holder_name"] = holder_name
    return metadata


def extract_credit_card_transactions(
    rows: dict[int, dict[int, Any]],
    header_row: int,
    column_map: dict[str, int],
    statement_path: Path,
    metadata: dict[str, str],
) -> list[Transaction]:
    transactions: list[Transaction] = []
    card_number = metadata.get("card_number", "")
    holder_name = metadata.get("holder_name", "")
    for row_index in sorted(rows):
        if row_index <= header_row:
            continue
        row = rows[row_index]
        if not row:
            continue
        row_text = " ".join(normalize_text(value) for value in row.values())
        upper_text = row_text.upper()
        if "REWARD POINTS SUMMARY" in upper_text or "GST SUMMARY" in upper_text:
            break

        description = normalize_text(row.get(column_map["description"], ""))
        amount = decimal_from_number(row.get(column_map["amount"]))
        statement_date, statement_time = parse_card_statement_datetime(row.get(column_map["date_time"]))
        if not description or amount is None or statement_date is None:
            continue

        credit_flag = normalize_text(row.get(column_map["debit_credit"], "")).upper()
        direction = "credit" if credit_flag in {"CR", "CREDIT"} else "debit"
        reference_match = re.search(r"Ref#\s*([0-9A-Za-z]+)", description, re.IGNORECASE)
        transaction_type = normalize_text(row.get(column_map.get("transaction_type", -1), ""))
        note_prefix = normalize_text(transaction_type)
        narration = description if not note_prefix else f"{note_prefix} | {description}"
        if statement_time:
            narration = f"{narration} | Time {statement_time}"

        transactions.append(
            Transaction(
                statement_path=statement_path,
                statement_kind="credit_card",
                account_number=card_number,
                account_name=holder_name,
                branch="",
                statement_from=None,
                statement_to=None,
                date=statement_date,
                value_date=statement_date,
                narration=narration,
                reference=reference_match.group(1) if reference_match else "",
                amount=amount,
                direction=direction,
                closing_balance=None,
                row_number=row_index + 1,
                holder_name=holder_name,
            )
        )
    return transactions


def parse_credit_card_statement_from_sheet(path: Path, sheet: SheetCells) -> Statement:
    rows = rows_from_cells(sheet.cells)
    header_row, column_map = find_credit_card_header(rows)
    metadata = extract_credit_card_metadata(rows, header_row)
    transactions = extract_credit_card_transactions(rows, header_row, column_map, path, metadata)
    if not transactions:
        raise ConversionError(f"No credit-card transactions found in {path.name} ({sheet.name}).")
    start_date = min(item.date for item in transactions)
    end_date = max(item.date for item in transactions)
    for item in transactions:
        item.statement_from = start_date
        item.statement_to = end_date
    return Statement(
        path=path,
        sheet_name=sheet.name,
        statement_kind="credit_card",
        account_number=metadata.get("card_number", ""),
        account_name=metadata.get("holder_name", ""),
        branch="",
        holder_name=metadata.get("holder_name", ""),
        statement_from=start_date,
        statement_to=end_date,
        transactions=transactions,
    )


def parse_statement_by_parser(path: Path, parser_id: str, password: str = "") -> Statement:
    normalized = normalize_text(parser_id).lower()
    if path.suffix.lower() == ".pdf":
        _ = read_pdf_text(path, password=password)
        raise ConversionError(
            f"PDF for parser '{normalized}' was opened successfully, but bank-specific PDF parsing is not implemented yet. Please provide an .xlsx/.xls sample if you want that parser added."
        )

    parser_map: dict[str, Any] = {
        "hdfc_bank": parse_bank_statement_from_sheet,
        "hdfc_credit_card": parse_credit_card_statement_from_sheet,
        "sbi_bank": parse_sbi_statement_from_sheet,
    }
    if normalized in {"ippb_bank"}:
        raise ConversionError(
            f"Parser '{normalized}' is configured but not implemented yet. Add one sample statement for this source and we can wire it cleanly."
        )
    parser = parser_map.get(normalized)
    if parser is None:
        raise ConversionError(f"Unknown parser '{parser_id}' configured for {path.name}.")

    for sheet in load_sheets(path, password=password):
        try:
            return parser(path, sheet)
        except ConversionError:
            continue
    raise ConversionError(f"Could not parse {path.name} using parser '{normalized}'.")


def parse_statement(path: Path, config: dict[str, Any] | None = None) -> Statement:
    if config:
        source_ids = candidate_source_ids(config, path)
        if source_ids:
            errors: list[str] = []
            for source_id in source_ids:
                source_config = (config.get("statement_sources", {}) or {}).get(source_id, {}) or {}
                parser_id = normalize_text(source_config.get("parser", ""))
                account_id = normalize_text(source_config.get("account_id", ""))
                password = password_for_source(config, source_id)
                try:
                    statement = parse_statement_by_parser(path, parser_id, password=password)
                    return bind_statement_identity(config, statement, source_id=source_id, account_id=account_id)
                except ConversionError as exc:
                    errors.append(f"{source_id}: {exc}")
            raise ConversionError("; ".join(errors))

    if path.suffix.lower() == ".pdf":
        raise ConversionError(
            f"No configured PDF parser is available for {path.name}. Add a source mapping and PDF reader support, or provide .xlsx/.xls."
        )

    for parser_id in ("hdfc_bank", "sbi_bank", "hdfc_credit_card"):
        try:
            statement = parse_statement_by_parser(path, parser_id)
            return bind_statement_identity(config or {}, statement)
        except ConversionError:
            continue
    raise ConversionError(f"Could not parse a supported statement from {path.name}.")


def parse_upi_narration(narration: str) -> NarrationDetails:
    details = NarrationDetails(kind="upi")
    prefix = "REV-UPI-" if narration.upper().startswith("REV-UPI-") else "UPI-"
    body = narration[len(prefix) :]
    tokens = [token for token in body.split("-")]
    vpa_index = next((index for index, token in enumerate(tokens) if "@" in token), -1)
    if vpa_index == -1:
        number_index = next((index for index, token in enumerate(tokens) if token.isdigit()), -1)
        if number_index != -1:
            details.payee = normalize_text("-".join(tokens[:number_index]))
            details.parsed_reference = tokens[number_index]
            details.note = format_upi_note("-".join(tokens[number_index + 1 :]), details.parsed_reference)
        else:
            details.payee = normalize_text(body)
        details.source_hint = prefix.rstrip("-")
        return details

    details.payee = normalize_text("-".join(tokens[:vpa_index]))
    details.vpa = normalize_text(tokens[vpa_index])
    tail = tokens[vpa_index + 1 :]
    if tail and not tail[0].isdigit():
        details.bank_code = normalize_text(tail[0])
        tail = tail[1:]
    if tail and tail[0].isdigit():
        details.parsed_reference = tail[0]
        tail = tail[1:]
    details.note = format_upi_note("-".join(tail), details.parsed_reference)
    details.source_hint = prefix.rstrip("-")
    return details


def parse_sbi_upi_narration(narration: str) -> NarrationDetails:
    details = NarrationDetails(kind="upi", source_hint="UPI")
    text = normalize_text(narration)
    bank_ref_match = re.search(r"\b([0-9]{10,})\s+AT\s+[0-9A-Z]+\b", text, re.IGNORECASE)
    if bank_ref_match:
        text = text[: bank_ref_match.start()].strip()

    upi_match = re.search(r"UPI/(CR|DR)/(.+)$", text, re.IGNORECASE)
    if not upi_match:
        details.payee = normalize_text(narration)
        return details

    tokens = [normalize_text(token) for token in upi_match.group(2).split("/") if normalize_text(token)]
    if tokens:
        details.parsed_reference = compact_text(tokens[0])
    if len(tokens) > 1:
        details.payee = normalize_text(tokens[1])
    if len(tokens) > 2:
        details.bank_code = compact_text(tokens[2]).upper()
    if len(tokens) > 3:
        details.vpa = compact_text(tokens[3])

    note_candidate = normalize_text(" / ".join(tokens[4:])) if len(tokens) > 4 else ""
    if note_candidate and len(compact_text(note_candidate)) >= 6:
        details.note = format_upi_note(note_candidate, details.parsed_reference)
    elif details.payee:
        details.note = format_upi_note(details.payee, details.parsed_reference)
    else:
        details.note = format_upi_note(note_candidate, details.parsed_reference)
    return details


def extract_narration_details(transaction: Transaction) -> NarrationDetails:
    upper = transaction.narration.upper()
    if transaction.statement_kind == "credit_card":
        parts = [normalize_text(part) for part in transaction.narration.split("|") if normalize_text(part)]
        description = next((part for part in parts if "UPI-" in part.upper() or "CC PAYMENT" in part.upper()), parts[0] if parts else transaction.narration)
        detail_note = " | ".join(part for part in parts if part != description)
        if description.upper().startswith("UPI-"):
            details = NarrationDetails(kind="card_upi")
            details.payee = normalize_text(description[4:])
            details.note = detail_note
            return details
        details = NarrationDetails(kind="card_payment" if "CC PAYMENT" in description.upper() else "credit_card")
        details.payee = normalize_text(description)
        details.note = detail_note
        ref_match = re.search(r"Ref#\s*([0-9A-Za-z]+)", description, re.IGNORECASE)
        if ref_match:
            details.parsed_reference = ref_match.group(1)
        return details

    if upper.startswith("UPI-") or upper.startswith("REV-UPI-"):
        return parse_upi_narration(transaction.narration)
    if "UPI/" in upper:
        return parse_sbi_upi_narration(transaction.narration)

    details = NarrationDetails()
    if "SALARY" in upper:
        details.kind = "salary"
        match = re.search(r"-(.+?)-SALARY-", transaction.narration, re.IGNORECASE)
        details.payee = normalize_text(match.group(1)) if match else "Salary Credit"
        salary_note = transaction.narration.split("-SALARY-", 1)[1] if "-SALARY-" in upper else ""
        details.note = normalize_text(salary_note)
        return details
    if upper.startswith("EMI "):
        details.kind = "emi"
        details.payee = "EMI"
        details.note = transaction.narration
        return details
    if "NEFT" in upper:
        details.kind = "neft"
    elif "INB" in upper:
        details.kind = "netbanking"
    elif "IMPS" in upper:
        details.kind = "imps"
    elif "ATM" in upper:
        details.kind = "atm"
    elif "POS" in upper:
        details.kind = "card"
    elif "REV" in upper or "RETURN" in upper or "REFUND" in upper:
        details.kind = "refund"
    else:
        details.kind = "generic"
    details.payee = normalize_text(transaction.narration)
    return details


def contains_any(text: str, needles: list[str]) -> bool:
    upper_text = text.upper()
    return any(normalize_text(needle).upper() in upper_text for needle in needles if needle)


def rule_matches(rule: dict[str, Any], transaction: Transaction, details: NarrationDetails) -> bool:
    text_pool = " | ".join(
        item
        for item in [
            transaction.narration,
            details.payee,
            details.note,
            details.vpa,
            transaction.reference,
            details.parsed_reference,
        ]
        if item
    ).upper()
    direction = normalize_text(rule.get("direction", "")).lower()
    if direction and direction != transaction.direction:
        return False

    kind = normalize_text(rule.get("kind", "")).lower()
    if kind and kind != details.kind.lower():
        return False

    contains_all = rule.get("contains_all", []) or []
    if contains_all and not all(normalize_text(value).upper() in text_pool for value in contains_all):
        return False

    contains_any_values = rule.get("contains_any", []) or []
    if contains_any_values and not contains_any(text_pool, [str(value) for value in contains_any_values]):
        return False

    regex = normalize_text(rule.get("regex", ""))
    if regex and not re.search(regex, text_pool, re.IGNORECASE):
        return False

    amount_min = decimal_from_number(rule.get("amount_min"))
    if amount_min is not None and transaction.amount < amount_min:
        return False

    amount_max = decimal_from_number(rule.get("amount_max"))
    if amount_max is not None and transaction.amount > amount_max:
        return False

    return True


def detect_counterpart_account(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
    account_config: dict[str, Any],
) -> str:
    counterpart_account_id = detect_counterpart_account_id(config, transaction, details, account_config)
    if counterpart_account_id:
        account_config = get_account_by_id(config, counterpart_account_id)
        resolved = normalize_text(account_config.get("money_manager_name", ""))
        if resolved:
            return resolved

    text_pool = " | ".join(
        item
        for item in [
            transaction.narration,
            details.payee,
            details.note,
            details.vpa,
            details.bank_code,
        ]
        if item
    ).upper()
    rules = list(config.get("transfer_targets", []) or []) + list(account_config.get("transfer_targets", []) or [])
    for rule in rules:
        contains_any_values = [str(item) for item in (rule.get("contains_any", []) or [])]
        if contains_any_values and contains_any(text_pool, contains_any_values):
            return resolve_account_reference(config, rule)
    return ""


def detect_counterpart_account_id(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
    account_config: dict[str, Any],
) -> str:
    text_pool = " | ".join(
        item
        for item in [
            transaction.narration,
            details.payee,
            details.note,
            details.vpa,
            details.bank_code,
        ]
        if item
    ).upper()
    rules = list(config.get("transfer_targets", []) or []) + list(account_config.get("transfer_targets", []) or [])
    for rule in rules:
        contains_any_values = [str(item) for item in (rule.get("contains_any", []) or [])]
        if contains_any_values and contains_any(text_pool, contains_any_values):
            account_id = resolve_account_reference_id(config, rule)
            if account_id:
                return account_id
    return ""


def get_identity_tokens(config: dict[str, Any], transaction: Transaction, account_config: dict[str, Any]) -> list[str]:
    tokens = []
    tokens.extend(config.get("identity", {}).get("names", []) or [])
    tokens.extend(config.get("identity", {}).get("vpas", []) or [])
    tokens.extend(config.get("identity", {}).get("keywords", []) or [])
    tokens.extend(account_config.get("identity_tokens", []) or [])
    if transaction.holder_name:
        tokens.append(transaction.holder_name)
    if transaction.account_number:
        tokens.append(transaction.account_number)
    return [normalize_text(token).upper() for token in tokens if normalize_text(token)]


def looks_like_own_transfer(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
    account_config: dict[str, Any],
) -> bool:
    text_pool = " | ".join(
        item
        for item in [
            transaction.narration,
            details.payee,
            details.note,
            details.vpa,
            transaction.reference,
        ]
        if item
    ).upper()
    tokens = get_identity_tokens(config, transaction, account_config)
    return any(token in text_pool for token in tokens)


def history_guess(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
) -> tuple[str, str, str, str] | None:
    history: HistoricalReference | None = config.get("_history")
    if history is None:
        return None
    text_pool = " ".join(
        part
        for part in [transaction.narration, details.payee, details.note, details.vpa, details.source_hint]
        if part
    )
    score_counter: Counter[tuple[str, str, str]] = Counter()
    for token in tokenize_history_text(text_pool, history.stopwords):
        for mapping, score in history.token_mappings.get(token, Counter()).items():
            score_counter[mapping] += score
    if not score_counter:
        return None

    best_mapping, best_score = score_counter.most_common(1)[0]
    second_score = score_counter.most_common(2)[1][1] if len(score_counter) > 1 else 0
    if best_score < history.min_score or best_score <= second_score:
        return None

    category, subcategory, historical_type = best_mapping
    if transaction.direction == "debit" and historical_type == "Income":
        return None
    if transaction.direction == "credit" and historical_type == "Expense":
        return None
    description = details.payee or normalize_text(transaction.narration)
    return historical_type, category, subcategory, description


def history_based_account_name(config: dict[str, Any], transaction: Transaction) -> str:
    history: HistoricalReference | None = config.get("_history")
    if history is None:
        return ""
    hints = config.get("history", {}).get("account_name_hints", {}) or {}
    if transaction.statement_kind == "credit_card":
        return history_account_hint(history, hints.get("credit_card_keywords", ["CARD"]))
    if any("SALARY" in item.narration.upper() for item in [transaction]):
        hinted = history_account_hint(history, hints.get("bank_account_keywords", ["SALARY"]))
        if hinted:
            return hinted
    return ""


def guess_defaults(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
    counterpart_account: str,
    own_transfer: bool,
) -> tuple[str, str, str, str]:
    money_manager = config["money_manager"]
    text_pool = " | ".join([transaction.narration, details.note, details.payee]).upper()

    if transaction.direction == "credit":
        if "SALARY" in text_pool or details.kind == "salary":
            return ("Income", "💰 Salary", "Salary 💵", details.payee or "Salary Credit")
        if "REFUND" in text_pool or "RETURN" in text_pool or "REV-UPI" in transaction.narration.upper():
            return ("Income", "Dept return to Me 💸💰", "", details.payee or "Refund")
        if own_transfer and counterpart_account:
            return ("Transfer-Out", counterpart_account, "", details.payee or counterpart_account)
        if own_transfer and money_manager.get("transfer_in_strategy", "income").lower() == "income":
            return (
                "Income",
                counterpart_account or normalize_text(money_manager.get("transfer_in_category", "Transfer In")),
                normalize_text(money_manager.get("transfer_in_subcategory", "")),
                details.payee or "Transfer In",
            )
        return (
            "Income",
            normalize_text(money_manager.get("default_income_category", "General Income")),
            normalize_text(money_manager.get("default_income_subcategory", "")),
            details.payee or "Credit",
        )

    if counterpart_account:
        return ("Transfer-Out", counterpart_account, "", details.payee or counterpart_account)

    keyword_rules = [
        (["RENT"], ("Expense", "pg rent", "pg rent", details.payee or "Rent")),
        (["EMI"], ("Expense", "Other", "Others", details.payee or "EMI")),
        (["SPOTIFY", "NETFLIX", "PRIME", "YOUTUBE"], ("Expense", "Subscribtion 👁️‍🗨️📀", "Spotify 🎵🎼", details.payee or "Subscription")),
        (["AWS", "AMAZONAWS", "CLOUD"], ("Expense", "Cloud Computing ☁️🖥️", "AWS Charges", details.payee or "Cloud")),
        (["RAPIDO"], ("Expense", "🚖 Transport", "rapido bike 🏍️", details.payee or "Transport")),
        (["UBER", "OLA", "CAB"], ("Expense", "🚖 Transport", "Cab 🚗🚕", details.payee or "Transport")),
        (["METRO"], ("Expense", "🚖 Transport", "Metro train 🚇", details.payee or "Transport")),
        (["BUS"], ("Expense", "🚖 Transport", "Bus 🚌", details.payee or "Transport")),
        (["TRAIN"], ("Expense", "🚖 Transport", "train 🚆🚂", details.payee or "Transport")),
        (["RECHARGE"], ("Expense", "📱 recharge", "", details.payee or "Recharge")),
        (["EGG", "BANANA", "PROTEIN", "PUMPKIN SEEDS", "SABJA"], ("Expense", "Gym expenses 💪🦾🏋️️", "Gym Food 🏋️️🍳🥚🍗", details.payee or "Gym Food")),
        (["CURD", "COCONUT", "ZEPTO", "SUPERMARKET", "MARKETPLACE"], ("Expense", "🥦 groceries", "", details.payee or "Groceries")),
        (["SOUP", "COFFEE", "TEA", "JUICE", "MILKSHAKE", "CAKE", "SNACK"], ("Expense", "🍜 Food", "snacks", details.payee or "Food")),
        (["NOODLES", "KFC", "KAPPI", "HOTEL", "CAFE", "BIRYANI", "CHICKEN", "DINNER"], ("Expense", "🍜 Food", "Dinner", details.payee or "Food")),
        (["LUNCH"], ("Expense", "🍜 Food", "Lunch", details.payee or "Food")),
        (["BREAKFAST", "IDLY", "POORI"], ("Expense", "🍜 Food", "Breakfast", details.payee or "Food")),
        (["POLICYBAZAAR", "INSURANCE"], ("Expense", "Insurances", "", details.payee or "Insurance")),
        (["DIAGNOSIS", "MEDICAL", "CLINIC", "LAB"], ("Expense", "Medical Expenses 💉💊", "Medicine or ointment or injection", details.payee or "Medical")),
        (["CINEMA", "BIGTREE", "MOVIE"], ("Expense", "Movie 🎥🍿", "", details.payee or "Movie")),
        (["BILLPAY", "CREDIT CARD"], ("Expense", "Other", "Others", details.payee or "Card Payment")),
        (["AURAGOLD", "GOLD"], ("Expense", "Gold/Silver ", "", details.payee or "Gold")),
        (["SIP", "WEALTH"], ("Expense", "SIP", "", details.payee or "Investment")),
        (["APPAREL", "CLOTHING"], ("Expense", "🧥 Apparel", "Clothing", details.payee or "Shopping")),
        (["SHOP", "MALL"], ("Expense", "Other", "Others", details.payee or "Shopping")),
    ]
    for keywords, result in keyword_rules:
        if contains_any(text_pool, keywords):
            return result

    historical_match = history_guess(config, transaction, details)
    if transaction.direction == "debit" and historical_match and historical_match[0] in {"Expense", "Transfer-Out"}:
        return historical_match
    if transaction.direction == "credit" and historical_match and historical_match[0] == "Income":
        return historical_match

    return (
        "Expense",
        normalize_text(money_manager.get("default_expense_category", "General Expense")),
        normalize_text(money_manager.get("default_expense_subcategory", "")),
        details.payee or "Debit",
    )


def build_note(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
) -> str:
    include_parsed_reference = not (
        transaction.statement_kind == "bank_account"
        and details.kind == "upi"
        and details.parsed_reference
        and f"({details.parsed_reference})" in details.note
    )
    return build_detail_text(
        config,
        transaction,
        details,
        include_note=True,
        include_parsed_reference=include_parsed_reference,
    )


def build_primary_note(transaction: Transaction, details: NarrationDetails) -> str:
    if transaction.statement_kind == "bank_account" and details.kind == "upi":
        short_note = normalize_text(details.note)
        if short_note.upper().startswith("EMPTY NOTE"):
            return "EMPTY NOTE"
        if re.fullmatch(r"\([0-9A-Za-z]+\)", short_note):
            return f"EMPTY NOTE {short_note}"
        if not short_note:
            return "EMPTY NOTE"
        return short_note
    if transaction.statement_kind == "bank_account":
        if details.kind == "salary":
            return normalize_text(details.note or details.payee or "Salary Credit")
        if details.kind == "emi":
            return normalize_text(transaction.narration)
        return normalize_text(details.payee or details.note or transaction.narration)
    if transaction.statement_kind == "credit_card":
        if details.parsed_reference:
            return f"EMPTY NOTE ({details.parsed_reference})"
        return "EMPTY NOTE"
    return ""


def build_detail_text(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
    *,
    include_note: bool,
    include_parsed_reference: bool,
) -> str:
    note_parts: list[str] = []
    if include_note and details.note:
        note_parts.append(details.note)
    if config["money_manager"].get("note_include_bank_reference", True) and transaction.reference:
        reference_label = "HDFC Ref" if normalize_text(transaction.source_id).startswith("hdfc") else "Bank Ref"
        note_parts.append(f"{reference_label}: {transaction.reference}")
    if include_parsed_reference and details.parsed_reference and details.parsed_reference != transaction.reference:
        note_parts.append(f"Txn Ref: {details.parsed_reference}")
    if config["money_manager"].get("note_include_vpa", True) and details.vpa:
        note_parts.append(details.vpa)
    if config["money_manager"].get("note_include_raw_narration", True):
        note_parts.append(f"Raw: {transaction.narration}")
    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in note_parts:
        cleaned = normalize_text(part)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_parts.append(cleaned)
    return " | ".join(unique_parts)


def combine_text_fields(*parts: str) -> str:
    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = normalize_text(part)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique_parts.append(cleaned)
    return " | ".join(unique_parts)


def account_config_for(
    config: dict[str, Any],
    account_number: str = "",
    account_id: str = "",
    source_id: str = "",
) -> dict[str, Any]:
    resolved_account_id = resolve_account_id(
        config,
        account_number=account_number,
        source_id=source_id,
        explicit_account_id=account_id,
    )
    if resolved_account_id:
        return get_account_by_id(config, resolved_account_id)
    return {}


def should_skip_transaction(
    config: dict[str, Any],
    transaction: Transaction,
    details: NarrationDetails,
) -> bool:
    if transaction.statement_kind != "credit_card" or transaction.direction != "credit":
        return False
    card_config = config.get("statement_types", {}).get("credit_card", {}) or {}
    if not card_config.get("skip_payment_credits", True):
        return False
    payment_keywords = [str(item) for item in (card_config.get("payment_credit_keywords", []) or [])]
    text_pool = " | ".join(
        part for part in [transaction.narration, details.payee, details.note, transaction.reference] if part
    ).upper()
    return contains_any(text_pool, payment_keywords)


def resolve_source_account_name(config: dict[str, Any], transaction: Transaction) -> str:
    account_config = account_config_for(
        config,
        account_number=transaction.account_number,
        account_id=transaction.account_id,
        source_id=transaction.source_id,
    )
    configured_name = normalize_text(account_config.get("money_manager_name", ""))
    if configured_name:
        return configured_name
    hinted = history_based_account_name(config, transaction)
    if hinted:
        return hinted
    prefix = normalize_text(config["money_manager"].get("fallback_account_prefix", "HDFC"))
    return title_from_masked_account(transaction.account_number, prefix)


def extract_transfer_candidate_ids(transaction: Transaction, details: NarrationDetails) -> tuple[str, ...]:
    identifiers: set[str] = set()
    for value in [transaction.reference, details.parsed_reference]:
        normalized = normalize_transaction_token(value)
        if normalized and len(normalized) >= 6:
            identifiers.add(normalized)
    return tuple(sorted(identifiers))


def is_identity_like_note(
    config: dict[str, Any],
    text: str,
    transactions: list[Transaction],
) -> bool:
    cleaned = normalize_text(text)
    if not cleaned:
        return False
    upper_text = cleaned.upper()
    for transaction in transactions:
        account_config = account_config_for(
            config,
            account_number=transaction.account_number,
            account_id=transaction.account_id,
            source_id=transaction.source_id,
        )
        for token in get_identity_tokens(config, transaction, account_config):
            if len(token) < 4:
                continue
            if token in upper_text or upper_text in token:
                return True
    return False


def choose_transfer_note(
    config: dict[str, Any],
    debit_candidate: TransferCandidate,
    credit_candidate: TransferCandidate,
) -> str:
    candidate_notes = [
        build_primary_note(debit_candidate.transaction, debit_candidate.details),
        build_primary_note(credit_candidate.transaction, credit_candidate.details),
        debit_candidate.details.note,
        credit_candidate.details.note,
        debit_candidate.details.payee,
        credit_candidate.details.payee,
    ]
    for note in candidate_notes:
        cleaned = normalize_text(note)
        if not cleaned:
            continue
        if cleaned.upper().startswith("EMPTY NOTE"):
            continue
        if re.fullmatch(r"\([0-9A-Za-z]+\)", cleaned):
            continue
        if is_identity_like_note(config, cleaned, [debit_candidate.transaction, credit_candidate.transaction]):
            continue
        return cleaned

    shared_ids = sorted(set(debit_candidate.normalized_ids) & set(credit_candidate.normalized_ids))
    if shared_ids:
        return f"Self Transfer ({shared_ids[0]})"
    return "Self Transfer"


def build_self_transfer_record(
    config: dict[str, Any],
    debit_candidate: TransferCandidate,
    credit_candidate: TransferCandidate,
) -> MoneyManagerRecord:
    source_transaction = debit_candidate.transaction
    mirror_transaction = credit_candidate.transaction
    source_account = resolve_source_account_name(config, source_transaction)
    counterpart_account = resolve_source_account_name(config, mirror_transaction)
    account_config = account_config_for(
        config,
        account_number=source_transaction.account_number,
        account_id=source_transaction.account_id,
        source_id=source_transaction.source_id,
    )
    currency = normalize_text(account_config.get("currency", config["money_manager"].get("default_currency", "INR"))) or "INR"
    shared_ids = sorted(set(debit_candidate.normalized_ids) & set(credit_candidate.normalized_ids))
    shared_id = shared_ids[0] if shared_ids else ""
    note = choose_transfer_note(config, debit_candidate, credit_candidate)

    description_parts = [f"Matched self transfer: {source_account} -> {counterpart_account}"]
    if shared_id:
        description_parts.append(f"Txn ID: {shared_id}")
    source_detail = build_detail_text(
        config,
        source_transaction,
        debit_candidate.details,
        include_note=False,
        include_parsed_reference=bool(debit_candidate.details.parsed_reference),
    )
    mirror_detail = build_detail_text(
        config,
        mirror_transaction,
        credit_candidate.details,
        include_note=False,
        include_parsed_reference=bool(credit_candidate.details.parsed_reference),
    )
    if source_detail:
        description_parts.append(f"Source: {source_detail}")
    if mirror_detail:
        description_parts.append(f"Mirror: {mirror_detail}")

    return MoneyManagerRecord(
        sort_date=source_transaction.date,
        date_text=format_date(source_transaction.date, config["output"]["date_format"]),
        source_account=source_account,
        category=counterpart_account,
        subcategory="",
        note=note,
        amount=source_transaction.amount,
        transaction_type="Transfer-Out",
        description=" | ".join(part for part in description_parts if part),
        counterpart_account=counterpart_account,
        currency=currency,
    )


def build_transfer_candidates(config: dict[str, Any], statements: list[Statement]) -> tuple[list[TransferCandidate], dict[str, int]]:
    candidates: list[TransferCandidate] = []
    counts: Counter[str] = Counter()
    transfer_like_keywords = ["UPI", "IMPS", "NEFT", "INB", "TFR", "TRANSFER", "PAYZAPP", "BILLPAY"]
    transfer_like_kinds = {"upi", "imps", "neft", "netbanking", "card_payment"}
    for statement in statements:
        stmt_key = statement_key(statement)
        for transaction in statement.transactions:
            details = extract_narration_details(transaction)
            account_config = account_config_for(
                config,
                account_number=transaction.account_number,
                account_id=transaction.account_id,
                source_id=transaction.source_id,
            )
            normalized_ids = extract_transfer_candidate_ids(transaction, details)
            counterpart_account_id = detect_counterpart_account_id(config, transaction, details, account_config)
            own_signal = looks_like_own_transfer(config, transaction, details, account_config) or bool(counterpart_account_id)
            text_pool = " | ".join(part for part in [transaction.narration, details.payee, details.note] if part).upper()
            transfer_like = details.kind in transfer_like_kinds or contains_any(text_pool, transfer_like_keywords)
            include = bool(counterpart_account_id) or (
                bool(normalized_ids) and transfer_like
            ) or (
                transaction.statement_kind == "credit_card" and transaction.direction == "credit"
            )
            if not include:
                continue
            candidates.append(
                TransferCandidate(
                    transaction_key=transaction_key(transaction),
                    statement_key=stmt_key,
                    transaction=transaction,
                    details=details,
                    amount=transaction.amount,
                    direction=transaction.direction,
                    source_account_id=transaction.account_id,
                    normalized_ids=normalized_ids,
                    counterpart_account_id=counterpart_account_id,
                    own_account_signal=own_signal,
                )
            )
            counts[stmt_key] += 1
    return candidates, dict(counts)


def choose_best_candidate_match(
    source_candidate: TransferCandidate,
    candidates: list[TransferCandidate],
) -> TransferCandidate | None:
    if not candidates:
        return None
    ranked: list[tuple[int, int, str, TransferCandidate]] = []
    source_ids = set(source_candidate.normalized_ids)
    for candidate in candidates:
        shared_id_count = len(source_ids & set(candidate.normalized_ids))
        day_gap = abs((candidate.transaction.date - source_candidate.transaction.date).days)
        score = shared_id_count * 100
        if source_candidate.own_account_signal:
            score += 15
        if candidate.own_account_signal:
            score += 15
        score -= day_gap * 5
        ranked.append((score, day_gap, candidate.transaction_key, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    best = ranked[0]
    if len(ranked) > 1 and ranked[1][:2] == best[:2]:
        return None
    return best[3]


def plan_transfer_matches(config: dict[str, Any], statements: list[Statement]) -> TransferMatchPlan:
    plan = TransferMatchPlan()
    candidates, candidate_counts = build_transfer_candidates(config, statements)
    plan.candidate_counts_by_statement = candidate_counts

    credit_index: dict[tuple[Decimal, str], list[TransferCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.transaction.statement_kind != "bank_account" or candidate.direction != "credit":
            continue
        for normalized_id in candidate.normalized_ids:
            credit_index[(candidate.amount, normalized_id)].append(candidate)

    for candidate in sorted(
        candidates,
        key=lambda item: (item.transaction.date, item.amount, item.transaction_key),
    ):
        if candidate.transaction_key in plan.suppressed_transaction_keys:
            continue
        if candidate.transaction.statement_kind != "bank_account" or candidate.direction != "debit":
            continue
        if not candidate.normalized_ids or not candidate.source_account_id:
            continue

        options: list[TransferCandidate] = []
        for normalized_id in candidate.normalized_ids:
            for mirror_candidate in credit_index.get((candidate.amount, normalized_id), []):
                if mirror_candidate.transaction_key in plan.suppressed_transaction_keys:
                    continue
                if mirror_candidate.source_account_id == candidate.source_account_id:
                    continue
                if abs((mirror_candidate.transaction.date - candidate.transaction.date).days) > 3:
                    continue
                options.append(mirror_candidate)

        mirror_candidate = choose_best_candidate_match(candidate, options)
        if mirror_candidate is None:
            continue

        synthetic_record = build_self_transfer_record(config, candidate, mirror_candidate)
        plan.synthetic_records_by_statement.setdefault(candidate.statement_key, []).append(synthetic_record)
        plan.synthetic_counts_by_statement[candidate.statement_key] = plan.synthetic_counts_by_statement.get(candidate.statement_key, 0) + 1

        for key, stmt_key in [
            (candidate.transaction_key, candidate.statement_key),
            (mirror_candidate.transaction_key, mirror_candidate.statement_key),
        ]:
            plan.suppressed_transaction_keys.add(key)
            plan.suppressed_counts_by_statement[stmt_key] = plan.suppressed_counts_by_statement.get(stmt_key, 0) + 1

        shared_ids = sorted(set(candidate.normalized_ids) & set(mirror_candidate.normalized_ids))
        transfer_id = shared_ids[0] if shared_ids else "unknown"
        plan.logs.append(
            f"Matched self transfer {candidate.amount} {resolve_source_account_name(config, candidate.transaction)} -> {resolve_source_account_name(config, mirror_candidate.transaction)} using txn id {transfer_id}."
        )

    payment_keywords = [
        str(item)
        for item in (config.get("statement_types", {}).get("credit_card", {}).get("payment_credit_keywords", []) or [])
    ]
    bank_transfer_candidates = [
        candidate
        for candidate in candidates
        if candidate.transaction.statement_kind == "bank_account"
        and candidate.direction == "debit"
        and candidate.counterpart_account_id
        and candidate.transaction_key not in plan.suppressed_transaction_keys
    ]
    credit_card_credit_candidates = [
        candidate
        for candidate in candidates
        if candidate.transaction.statement_kind == "credit_card"
        and candidate.direction == "credit"
        and candidate.transaction_key not in plan.suppressed_transaction_keys
    ]

    for candidate in sorted(
        credit_card_credit_candidates,
        key=lambda item: (item.transaction.date, item.amount, item.transaction_key),
    ):
        text_pool = " | ".join(
            part for part in [candidate.transaction.narration, candidate.details.payee, candidate.details.note, candidate.transaction.reference] if part
        ).upper()
        if payment_keywords and not contains_any(text_pool, payment_keywords):
            continue

        options = [
            bank_candidate
            for bank_candidate in bank_transfer_candidates
            if bank_candidate.counterpart_account_id == candidate.source_account_id
            and bank_candidate.amount == candidate.amount
            and abs((bank_candidate.transaction.date - candidate.transaction.date).days) <= 3
        ]
        mirror_candidate = choose_best_candidate_match(candidate, options)
        if mirror_candidate is None:
            continue

        plan.suppressed_transaction_keys.add(candidate.transaction_key)
        plan.suppressed_counts_by_statement[candidate.statement_key] = plan.suppressed_counts_by_statement.get(candidate.statement_key, 0) + 1
        plan.logs.append(
            f"Suppressed mirrored credit-card payment entry {candidate.amount} on {candidate.transaction.date.isoformat()} because the matching bank transfer was already exported."
        )

    return plan


def transaction_to_money_manager_record(
    config: dict[str, Any],
    transaction: Transaction,
    warnings: list[str],
) -> MoneyManagerRecord:
    account_config = account_config_for(
        config,
        account_number=transaction.account_number,
        account_id=transaction.account_id,
        source_id=transaction.source_id,
    )
    details = extract_narration_details(transaction)
    if should_skip_transaction(config, transaction, details):
        raise ConversionError("Skipped credit-card payment credit because the matching bank-account transfer should carry it.")
    counterpart_account = detect_counterpart_account(config, transaction, details, account_config)
    own_transfer = looks_like_own_transfer(config, transaction, details, account_config)
    transaction_type, category, subcategory, description = guess_defaults(
        config,
        transaction,
        details,
        counterpart_account,
        own_transfer,
    )

    for rule in config.get("rules", []) or []:
        if not isinstance(rule, dict) or not rule_matches(rule, transaction, details):
            continue
        transaction_type = normalize_money_manager_type(rule.get("transaction_type")) or transaction_type
        category = normalize_text(rule.get("category", category)) or category
        subcategory = normalize_text(rule.get("subcategory", subcategory))
        description = normalize_text(rule.get("description", description)) or description
        counterpart_account = resolve_account_reference(config, rule) or counterpart_account
        note_override = normalize_text(rule.get("note", ""))
        if note_override:
            details.note = note_override

    source_account = resolve_source_account_name(config, transaction)

    if transaction.direction == "debit" and counterpart_account:
        transaction_type = "Transfer-Out"
        category = counterpart_account
        description = description or counterpart_account

    if transaction_type == "Transfer-Out":
        if not counterpart_account:
            transaction_type = "Expense"
            explicit_transfer_hint = contains_any(
                " | ".join([transaction.narration, details.payee, details.note, transaction.reference]),
                ["BILLPAY", "CC PAYMENT", "PAYZAPP", "SELF TRANSFER"],
            ) or own_transfer
            if explicit_transfer_hint:
                warnings.append(
                    f"{transaction.statement_path.name} row {transaction.row_number}: looked like a transfer but no destination account mapping was found, so it was exported as an expense."
                )
        else:
            category = counterpart_account
            description = description or counterpart_account

    if not account_config.get("money_manager_name"):
        if not history_based_account_name(config, transaction):
            warnings.append(
                f"{transaction.statement_path.name}: account {transaction.account_number or 'UNKNOWN'} is not mapped in config.yml, so a fallback Money Manager account name was used."
            )

    currency = normalize_text(account_config.get("currency", config["money_manager"].get("default_currency", "INR"))) or "INR"
    primary_note = build_primary_note(transaction, details)
    note = primary_note or build_note(config, transaction, details)
    if transaction.statement_kind == "bank_account" and details.kind == "upi":
        note = primary_note
        description = build_detail_text(
            config,
            transaction,
            details,
            include_note=False,
            include_parsed_reference=not (details.parsed_reference and f"({details.parsed_reference})" in primary_note),
        ) or description
    elif transaction.statement_kind == "credit_card":
        note = primary_note
        description = build_detail_text(
            config,
            transaction,
            details,
            include_note=True,
            include_parsed_reference=bool(details.parsed_reference),
        ) or description
    else:
        note = primary_note or description or normalize_text(transaction.narration)
        detail_text = build_detail_text(
            config,
            transaction,
            details,
            include_note=False,
            include_parsed_reference=bool(details.parsed_reference),
        )
        base_description = description
        if base_description == note or base_description == details.payee or base_description == normalize_text(transaction.narration):
            base_description = ""
        description = combine_text_fields(base_description, detail_text) or description or note
    record = MoneyManagerRecord(
        sort_date=transaction.date,
        date_text=format_date(transaction.date, config["output"]["date_format"]),
        source_account=source_account,
        category=category,
        subcategory=subcategory,
        note=note,
        amount=transaction.amount,
        transaction_type=transaction_type,
        description=description or normalize_text(transaction.narration),
        counterpart_account=counterpart_account,
        currency=currency,
    )
    return record


def read_template_from_xlsx(path: Path) -> OutputTemplate:
    sheets = parse_xlsx_sheets(path)
    if not sheets:
        raise ConversionError(f"No sheets were found in template workbook {path}.")
    sheet = sheets[0]
    rows = rows_from_cells(sheet.cells)
    if 0 not in rows:
        raise ConversionError(f"Template workbook {path} does not have a header row.")
    header_row = rows[0]
    max_col = max(header_row) if header_row else -1
    headers = [normalize_text(header_row.get(col, "")) for col in range(max_col + 1)]
    return OutputTemplate(headers=headers, sheet_name=sheet.name or "Money Manager", template_mode="from_sample")


def resolve_output_template(config: dict[str, Any], output_directory: Path) -> OutputTemplate:
    mode = normalize_text(config["output"].get("template_mode", "auto")).lower() or "auto"
    sample_path = normalize_text(config["output"].get("template_sample", ""))
    if mode in {"auto", "from_sample"}:
        template_file = Path(sample_path) if sample_path else None
        if template_file and not template_file.is_absolute():
            template_file = Path.cwd() / template_file
        if template_file and template_file.exists():
            return read_template_from_xlsx(template_file)
        sample_candidates = sorted(output_directory.glob("*.xlsx"))
        if sample_candidates:
            return read_template_from_xlsx(sample_candidates[0])
        if mode == "from_sample":
            raise ConversionError("Template mode is 'from_sample' but no sample .xlsx template was found.")

    if mode == "official_sub_currency":
        return OutputTemplate(
            headers=[
                "Date",
                "Account",
                "Category",
                "Subcategory",
                "Note",
                "Amount",
                "Income/Expense",
                "Description",
                "Amount Sub",
                "Currency",
            ],
            sheet_name="Money Manager",
            template_mode="official_sub_currency",
        )

    return OutputTemplate(
        headers=["Date", "Account", "Category", "Subcategory", "Note", "Amount", "Income/Expense", "Description"],
        sheet_name="Money Manager",
        template_mode="official_basic",
    )


def render_record(template: OutputTemplate, record: MoneyManagerRecord) -> list[Any]:
    values: list[Any] = []
    account_occurrence = 0
    amount_occurrence = 0
    for header in template.headers:
        normalized = normalize_label(header)
        if normalized == "DATE":
            values.append(record.date_text)
        elif normalized == "ACCOUNT":
            if account_occurrence == 0:
                values.append(record.source_account)
            else:
                values.append(record.counterpart_account)
            account_occurrence += 1
        elif normalized == "CATEGORY":
            values.append(record.category)
        elif normalized == "SUBCATEGORY":
            values.append(record.subcategory)
        elif normalized == "NOTE":
            values.append(record.note)
        elif normalized in {"INCOMEEXPENSE", "TYPE"}:
            values.append(record.transaction_type)
        elif normalized == "DESCRIPTION":
            values.append(record.description)
        elif normalized == "CURRENCY":
            values.append(record.sub_currency)
        elif normalized in {"AMOUNTSUB", "SUBAMOUNT"}:
            values.append(record.sub_amount)
            amount_occurrence += 1
        elif normalized == "AMOUNT":
            if amount_occurrence == 0:
                values.append(record.amount)
            else:
                values.append(record.sub_amount)
            amount_occurrence += 1
        elif ISO_CURRENCY_RE.fullmatch(normalize_text(header).upper() or ""):
            values.append(record.amount)
            amount_occurrence += 1
        else:
            values.append("")
    return values


def sanitize_xml_text(value: str) -> str:
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)


def xlsx_cell_xml(ref: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, Decimal):
        return f'<c r="{ref}"><v>{format_amount(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = sanitize_xml_text(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


def write_xlsx(path: Path, sheet_name: str, rows: list[list[Any]]) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    sheet_rows: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row):
            cell = xlsx_cell_xml(f"{index_to_column_letters(col_index)}{row_index}", value)
            if cell:
                cells.append(cell)
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData>"
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        "<sheets>"
        f'<sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/>'
        "</sheets>"
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        "<dc:creator>money_manager_csv_converter</dc:creator>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now.isoformat().replace('+00:00', 'Z')}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now.isoformat().replace('+00:00', 'Z')}</dcterms:modified>"
        "</cp:coreProperties>"
    )
    app_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Python</Application>"
        "</Properties>"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/core.xml", core_xml)
        archive.writestr("docProps/app.xml", app_xml)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles_xml)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def write_tsv(path: Path, rows: list[list[Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            rendered = []
            for value in row:
                if isinstance(value, Decimal):
                    rendered.append(format_amount(value))
                else:
                    rendered.append("" if value is None else str(value))
            writer.writerow(rendered)


def resolve_input_files(config: dict[str, Any], cli_paths: list[str]) -> list[Path]:
    if cli_paths:
        return [Path(item).resolve() for item in cli_paths]

    input_dir = Path(config["input"]["directory"]).resolve()
    recursive = bool(config["input"].get("recursive", False))
    files: list[Path] = []
    for pattern in config["input"].get("patterns", ["*.xls", "*.xlsx"]):
        if recursive:
            files.extend(path.resolve() for path in input_dir.rglob(pattern))
        else:
            files.extend(path.resolve() for path in input_dir.glob(pattern))
    unique_files = sorted({path for path in files if path.is_file()})
    return unique_files


def date_range_for_records(records: list[MoneyManagerRecord]) -> tuple[str, str]:
    dates = [datetime.strptime(record.date_text, DEFAULT_DATE_OUTPUT_FORMAT).date() for record in records if record.date_text]
    if not dates:
        return ("unknown", "unknown")
    return (min(dates).isoformat(), max(dates).isoformat())


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "statement"


def statement_file_stem(statement: Statement) -> str:
    start = statement.statement_from.isoformat() if statement.statement_from else "unknown_from"
    end = statement.statement_to.isoformat() if statement.statement_to else "unknown_to"
    account = statement.account_id or statement.account_number or statement.source_id or statement.path.stem
    return f"{slugify(account)}_{start}_to_{end}"


def statement_account_name(config: dict[str, Any], statement: Statement) -> str:
    account_config = account_config_for(
        config,
        account_number=statement.account_number,
        account_id=statement.account_id,
        source_id=statement.source_id,
    )
    configured_name = normalize_text(account_config.get("money_manager_name", ""))
    if configured_name:
        return configured_name
    if statement.transactions:
        return resolve_source_account_name(config, statement.transactions[0])
    return statement.account_name or statement.account_number or statement.source_id or statement.path.stem


def statement_totals(statement: Statement) -> tuple[int, int, Decimal, Decimal]:
    debit_count = 0
    credit_count = 0
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    for transaction in statement.transactions:
        if transaction.direction == "debit":
            debit_count += 1
            debit_total += transaction.amount
        elif transaction.direction == "credit":
            credit_count += 1
            credit_total += transaction.amount
    return debit_count, credit_count, debit_total, credit_total


def print_statement_parse_summary(config: dict[str, Any], statement: Statement) -> None:
    debit_count, credit_count, debit_total, credit_total = statement_totals(statement)
    account_name = statement_account_name(config, statement)
    start = statement.statement_from.isoformat() if statement.statement_from else "unknown"
    end = statement.statement_to.isoformat() if statement.statement_to else "unknown"
    print(f"Statement parsed: {statement.path.name}")
    print(f"  Source: {statement.source_id or 'unknown'} | Account: {account_name}")
    print(f"  Period: {start} to {end}")
    print(
        f"  Transactions: {len(statement.transactions)} | Debits: {debit_count} ({format_amount(debit_total)}) | Credits: {credit_count} ({format_amount(credit_total)})"
    )


def print_statement_export_summary(
    config: dict[str, Any],
    statement: Statement,
    plan: TransferMatchPlan,
    exported_records: list[MoneyManagerRecord],
) -> None:
    stmt_key = statement_key(statement)
    print(f"Statement exported: {statement.path.name}")
    print(
        f"  Account: {statement_account_name(config, statement)} | Export rows: {len(exported_records)} | Transfer candidates: {plan.candidate_counts_by_statement.get(stmt_key, 0)}"
    )
    print(
        f"  Synthetic self transfers: {plan.synthetic_counts_by_statement.get(stmt_key, 0)} | Suppressed mirrored entries: {plan.suppressed_counts_by_statement.get(stmt_key, 0)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert bank and card statements into Money Manager import files.")
    parser.add_argument("paths", nargs="*", help="Optional input statement files. Defaults to config.yml input patterns.")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    input_files = resolve_input_files(config, args.paths)
    if not input_files:
        print("No input statements were found.", file=sys.stderr)
        return 1

    output_dir = Path(config["output"]["directory"]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config["_history"] = load_historical_reference(config, output_dir)
    template = resolve_output_template(config, output_dir)

    statements: list[Statement] = []
    warnings: list[str] = []
    for input_path in input_files:
        try:
            statement = parse_statement(input_path, config)
            statements.append(statement)
            print_statement_parse_summary(config, statement)
        except Exception as exc:
            warnings.append(f"{input_path.name}: {exc}")

    if not statements:
        print("No statements could be parsed.", file=sys.stderr)
        for warning in warnings:
            print(f"WARNING: {warning}")
        return 1

    transfer_plan = plan_transfer_matches(config, statements)
    if transfer_plan.logs:
        print("Transfer matching:")
        for line in transfer_plan.logs:
            print(f"  - {line}")

    individual_outputs: list[Path] = []
    combined_records: list[MoneyManagerRecord] = []

    for statement in statements:
        stmt_key = statement_key(statement)
        records: list[MoneyManagerRecord] = list(transfer_plan.synthetic_records_by_statement.get(stmt_key, []))
        for item in statement.transactions:
            if transaction_key(item) in transfer_plan.suppressed_transaction_keys:
                continue
            try:
                records.append(transaction_to_money_manager_record(config, item, warnings))
            except ConversionError as exc:
                warnings.append(f"{item.statement_path.name} row {item.row_number}: {exc}")
        records.sort(key=lambda record: (record.sort_date, record.source_account, record.amount, record.description))
        combined_records.extend(records)
        print_statement_export_summary(config, statement, transfer_plan, records)
        rows = [template.headers] + [render_record(template, record) for record in records]
        stem = statement_file_stem(statement)
        if config["output"].get("write_individual_files", True):
            if config["output"].get("write_xlsx", True):
                target = output_dir / f"{stem}.xlsx"
                try:
                    write_xlsx(target, template.sheet_name, rows)
                    individual_outputs.append(target)
                except PermissionError:
                    warnings.append(f"Could not write {target.name} because the file is open or locked.")
            if config["output"].get("write_tsv", True):
                target = output_dir / f"{stem}.tsv"
                try:
                    write_tsv(target, rows)
                    individual_outputs.append(target)
                except PermissionError:
                    warnings.append(f"Could not write {target.name} because the file is open or locked.")

    combined_outputs: list[Path] = []
    if config["output"].get("combine_statements", True):
        combined_records.sort(key=lambda record: (record.sort_date, record.source_account, record.amount, record.description))
        rows = [template.headers] + [render_record(template, record) for record in combined_records]
        base_name = slugify(config["output"].get("combined_file_name", "money_manager_import_all_accounts"))
        if config["output"].get("write_xlsx", True):
            target = output_dir / f"{base_name}.xlsx"
            try:
                write_xlsx(target, template.sheet_name, rows)
                combined_outputs.append(target)
            except PermissionError:
                warnings.append(f"Could not write {target.name} because the file is open or locked.")
        if config["output"].get("write_tsv", True):
            target = output_dir / f"{base_name}.tsv"
            try:
                write_tsv(target, rows)
                combined_outputs.append(target)
            except PermissionError:
                warnings.append(f"Could not write {target.name} because the file is open or locked.")

    print(f"Parsed {len(statements)} statement(s) and exported {len(combined_records)} transaction(s).")
    print(f"Template mode: {template.template_mode} -> {', '.join(template.headers)}")
    history: HistoricalReference | None = config.get("_history")
    if history and history.source_path:
        print(f"Historical mapping source: {history.source_path}")
    if individual_outputs:
        print("Individual outputs:")
        for path in individual_outputs:
            print(f"  - {path}")
    if combined_outputs:
        print("Combined outputs:")
        for path in combined_outputs:
            print(f"  - {path}")
    if warnings:
        print("Warnings:")
        for warning in dict.fromkeys(warnings):
            print(f"  - {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
