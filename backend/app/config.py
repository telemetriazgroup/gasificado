from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://gasificado:gasificado@db:5432/gasificado"
    tcp_bridge_url: str = "http://tcp_bridge:8081"
    legacy_api_url: str = ""
    legacy_api_url2: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
