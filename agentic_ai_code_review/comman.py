import os
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