import os
import json
import re
from typing import List, Dict
class CommonUtils:
    def get_env_value(self, env_path: str, key: str, default=None):
        """
        Load a .env file from the given path and return the value for a key.
        Args:
            env_path (str): Absolute or relative path to the .env file
            key (str): Environment variable key to retrieve
            default: Value to return if key is not found
        Returns:
            str | None: Value for the key or default if not found
        Raises:
            FileNotFoundError: If the .env file does not exist
            ValueError: If the .env file is malformed
        """

        if not os.path.isfile(env_path):
            raise FileNotFoundError(f".env file not found at: {env_path}")

        value = None

        with open(env_path, "r", encoding="utf-8") as env_file:
            for line_no, line in enumerate(env_file, start=1):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                if "=" not in line:
                    raise ValueError(
                        f"Invalid line in .env file at line {line_no}: {line}"
                    )

                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")

                if k == key:
                    value = v
                    break

        return value if value is not None else default
    
    class JSONExtractionError(Exception):
        pass
    # def extract_json_from_ai_output(self, text: str):
    #     """
    #     Extract valid JSON (dict or list) from ANY AI output.

    #     Handles:
    #     - Raw JSON
    #     - ```json fenced blocks
    #     - JSON embedded in text
    #     - Multiple JSONs (returns the most complete one)
    #     - Smart quotes, trailing commas
    #     - Extra text before/after JSON

    #     Returns:
    #         dict | list

    #     Raises:
    #         JSONExtractionError
    #     """

    #     if not text or not isinstance(text, str):
    #         raise self.JSONExtractionError("Invalid input")

    #     import json
    #     import re

    #     text = text.strip()

    #     # ---------- Normalization ----------
    #     def normalize(s: str) -> str:
    #         s = (
    #             s.replace("“", '"')
    #             .replace("”", '"')
    #             .replace("‘", "'")
    #             .replace("’", "'")
    #             .replace("\u00a0", " ")
    #         )
    #         s = re.sub(r",\s*([}\]])", r"\1", s)  # remove trailing commas
    #         return s.strip()

    #     # ---------- 1. Direct parse ----------
    #     try:
    #         return json.loads(normalize(text))
    #     except Exception:
    #         pass

    #     # ---------- 2. Markdown fenced blocks ----------
    #     fence_regex = re.compile(
    #         r"```(?:json)?\s*(.*?)\s*```",
    #         re.DOTALL | re.IGNORECASE
    #     )

    #     for block in fence_regex.findall(text):
    #         try:
    #             return json.loads(normalize(block))
    #         except Exception:
    #             continue

    #     # ---------- 3. String-aware brace matching ----------
    #     candidates = []
    #     stack = []
    #     start = None
    #     in_string = False
    #     escape = False

    #     for i, ch in enumerate(text):
    #         if ch == '"' and not escape:
    #             in_string = not in_string

    #         elif not in_string:
    #             if ch in "{[":
    #                 if not stack:
    #                     start = i
    #                 stack.append(ch)

    #             elif ch in "}]":
    #                 if stack:
    #                     stack.pop()
    #                     if not stack and start is not None:
    #                         candidates.append(text[start:i + 1])
    #                         start = None

    #         escape = (ch == "\\" and not escape)

    #     # ---------- 4. Normalize & parse candidates ----------
    #     parsed = []

    #     for c in candidates:
    #         try:
    #             parsed.append(json.loads(normalize(c)))
    #         except Exception:
    #             continue

    #     if parsed:
    #         # Prefer dicts over lists, then larger structures
    #         def score(x):
    #             base = len(json.dumps(x))
    #             return base + (1000 if isinstance(x, dict) else 0)

    #         return max(parsed, key=score)

    #     # ---------- 5. Last-resort extraction ----------
    #     start = min(
    #         (text.find("{") if "{" in text else float("inf")),
    #         (text.find("[") if "[" in text else float("inf")),
    #     )
    #     end = max(text.rfind("}"), text.rfind("]"))

    #     if start != float("inf") and end != -1 and end > start:
    #         try:
    #             return json.loads(normalize(text[start:end + 1]))
    #         except Exception:
    #             pass

    #     raise self.JSONExtractionError("No valid JSON found in AI output")

    
    
    def extract_json_from_ai_output(self, text: str) -> dict:
        if not text or not isinstance(text, str):
            raise self.JSONExtractionError("Empty or invalid AI output")

        text = text.strip()

        # Remove surrounding quotes
        if (text.startswith("'") and text.endswith("'")) or \
           (text.startswith('"') and text.endswith('"')):
            text = text[1:-1].strip()

        # Extract JSON from ```json ... ```
        fenced = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL
        )
        if fenced:
            json_str = fenced.group(1)
        else:
            # Fallback: first {...}
            brace = re.search(r"(\{.*\})", text, re.DOTALL)
            if not brace:
                raise self.JSONExtractionError("No JSON object found")
            json_str = brace.group(1)

        # 🔧 CRITICAL FIX: sanitize invalid JSON escapes
        json_str = self._sanitize_invalid_json_escapes(json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise self.JSONExtractionError(
                f"JSON parsing failed after sanitization: {e}"
            )

    def _sanitize_invalid_json_escapes(self, s: str) -> str:
        """
        Fixes invalid JSON escape sequences commonly produced by LLMs.
        """
        # Replace \' with '
        s = s.replace("\\'", "'")

        # OPTIONAL: fix other rare AI mistakes
        s = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', s)

        return s
    def merge_consecutive_diffs(self, diffs: List[Dict]) -> List[Dict]:
        if not diffs:
            return []

        merged = []
        current = diffs[0]

        def is_consecutive(prev, curr):
            same_file = prev["diff"]["file_path"] == curr["diff"]["file_path"]
            consecutive_line = curr["diff"]["new_start_line_number"] == prev["diff"]["new_start_line_number"] + prev["diff"]["number_of_lines_added_in_new"]
            return same_file and consecutive_line

        for i in range(1, len(diffs)):
            prev = current
            curr = diffs[i]

            if is_consecutive(prev, curr):
                prev_diff = current["diff"]
                curr_diff = curr["diff"]

                prev_diff["new_start_line_number"] = curr_diff["new_start_line_number"]

                prev_diff["new_content"] = (
                    prev_diff["new_content"] + "\n" + curr_diff["new_content"]
                    if prev_diff["new_content"] and curr_diff["new_content"]
                    else prev_diff["new_content"] or curr_diff["new_content"]
                )

                prev_diff["old_content"] = (
                    prev_diff["old_content"] + "\n" + curr_diff["old_content"]
                    if prev_diff["old_content"] and curr_diff["old_content"]
                    else prev_diff["old_content"] or curr_diff["old_content"]
                )

                current["categories"] = sorted(
                    set(current["categories"] + curr["categories"]),
                    key=["critical", "high", "medium", "low"].index
                )

                if curr.get("explanation"):
                    current["explanation"] += " " + curr["explanation"]

                if curr.get("comments"):
                    current["comments"] += "\n" + curr["comments"] if current["comments"] else curr["comments"]

            else:
                merged.append(current)
                current = curr

        merged.append(current)
        return merged
