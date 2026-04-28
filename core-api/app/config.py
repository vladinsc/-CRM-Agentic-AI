from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    google_secrets_path: str #= "secrets/client_secret.json"
    database_url: str
    # Configurare pentru a citi si din fisier daca variabilele de mediu lipsesc
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()