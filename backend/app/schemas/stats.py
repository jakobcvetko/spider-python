from datetime import date

from pydantic import BaseModel


class DailyMatchCountOut(BaseModel):
    date: date
    count: int


class DailyMatchesOut(BaseModel):
    days: list[DailyMatchCountOut]
    total: int
