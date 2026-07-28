"""Contrat d'API du calendrier tamrielien.

`GET /api/v1/calendar` renvoie le calendrier **complet** en une fois — c'est
délibéré. L'ancienne UI faisait deux allers-retours HTMX pour ça : `/suggest-date`
au changement de catégorie et `/date-days` au changement de mois, uniquement pour
recalculer les bornes du menu « jour ». Ces données sont statiques (12 mois, un
nombre de jours fixe chacun) : le client les charge une fois et calcule localement.
"""

from pydantic import BaseModel, Field

from backend.core import tamrielic_calendar as calendar


class Month(BaseModel):
    index: int
    name_en: str = Field(description="Nom utilisé dans la date stockée")
    name_fr: str
    days: int


class GameDate(BaseModel):
    """Date de session décomposée en composants."""

    era: int = Field(ge=1)
    year: int = Field(ge=1)
    month_index: int = Field(ge=0, le=11)
    day: int = Field(ge=1, le=31)

    def to_stored_string(self) -> str:
        """Assemble la forme stockée « Evening Star, 15th, 4E 201 ».

        Le jour est ramené dans les bornes du mois : un 31 en Sun's Dawn devient 28
        plutôt que de produire une date impossible.
        """
        day = calendar.clamp_day(self.month_index, self.day)
        return calendar.format_date(self.era, self.year, self.month_index, day)


class CalendarOut(BaseModel):
    """Toutes les données nécessaires pour construire le sélecteur de date."""

    eras: list[int]
    months: list[Month]
    weekdays: list[str]
    default: GameDate


class SuggestedDateOut(BaseModel):
    """Date proposée par défaut pour une catégorie."""

    date: GameDate
    source: str = Field(
        description="'last_known' si tirée du XML de la catégorie, 'default' sinon"
    )
    stored: str = Field(description="Forme stockée correspondante")
