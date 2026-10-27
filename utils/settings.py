import os
import sys
import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from opencast.opencast import Opencast

logging.basicConfig(stream=sys.stdout,
        level=logging.INFO,
        format='%(asctime)s %(process)d %(levelname)-8s %(filename)s(%(lineno)d) %(message)s')

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger()

DEFAULT_ENV_FILES = [
    "/run/secrets/passwords",
    "/usr/local/serverconfig/recording.cfg",
    ".env"
]

env_file = next((f for f in DEFAULT_ENV_FILES if os.path.exists(f)), None)

# This line references a path for secret loading, but does not embed a secret.
class FetchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_file,
                                        env_file_encoding='utf-8',
                                        frozen=False,
                                        extra='ignore')

    # Store the env_file path manually
    _env_file_used: str | None = None

    ROOT_PATH: str = Field(default='/', validation_alias='ROOT_PATH')

    TITLE: str = Field(default='Capture Agent Status Service', description='The title of the service.')
    VERSION: str = Field(default='0.0.1')

    SERVER_TYPE: str = Field(default='dev', validation_alias='ENV', description='The environment type (e.g., dev, prod).')
    SERVER_DEBUG: bool = Field(default=False, validation_alias='DEBUG', description='Is the system running in debug mode.')
    SERVER_IN_DOCKER: bool = Field(default=False, validation_alias='RUNNING_IN_DOCKER', description='Is the system running in docker.')

    REDIS_HOST: str = Field(default='localhost', validation_alias='REDIS_HOST', description='Redis host.')
    REDIS_PASSWORD: str = Field(default='', validation_alias='REDIS_PASSWORD', description='Redis password.')
    REDIS_PORT: int = Field(default=6379, validation_alias='REDIS_PORT', description='Redis port.')
    REDIS_CLEAN_START: bool = Field(default=False, validation_alias='REDIS_CLEAN_START', description='Whether to clear Redis on startup.')

    OC_HOST: str = Field(default='localhost', validation_alias='OC_SERVER', description='Opencast server URL.')
    OC_USER: str = Field(default='opencast', validation_alias='OC_USER', description='Opencast username.')
    OC_PASS: str = Field(default='password', validation_alias='OC_PASS', description='Opencast password.')

    # Helpdesk contact
    CONTACT_EMAIL: str = Field(default='helpdesk@example.com', validation_alias='CONTACT_EMAIL', description='Helpdesk contact email.')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Save env_file if passed explicitly
        self._env_file_used = kwargs.get('_env_file', env_file)
        logger.debug(f"Using env file: {self._env_file_used}")

        self.SERVER_TYPE = kwargs.get('SERVER_TYPE', self.SERVER_TYPE)

        # if we are running as script then we don't need the rest of the initialization to happen
        if 'script' in self.SERVER_TYPE:
            return

        # explicitly set self.Redis_password, was returning the file path name
        password_file = "/run/secrets/redis_password"

        if os.path.exists(password_file):
            try:
                with open(password_file, "r") as f:
                    self.REDIS_PASSWORD = f.read().strip()

                logger.debug(f"Redis password loaded from secret file (length: {len(self.REDIS_PASSWORD)})")
            except Exception as e:
                logger.error(f"Failed to read Redis password file: {e}")
                self.REDIS_PASSWORD = ""
        else:
            logger.warning("Redis password file not found at /run/secrets/redis_password — connecting without password")
            self.REDIS_PASSWORD = ""

    @property
    def OC(self) -> Opencast:
        """Create a Opencast client instance."""
        return Opencast(
            server=self.OC_HOST,
            username=self.OC_USER,
            password=self.OC_PASS,
        )

    @field_validator("SERVER_DEBUG", "SERVER_IN_DOCKER", mode="before")
    @classmethod
    def validate_bool(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "1", "yes"):
            return True
        if isinstance(value, str) and value.lower() in ("false", "0", "no"):
            return False
        return False
