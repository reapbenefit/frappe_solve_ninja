# Copyright (c) 2026, ReapBenefit and contributors
# For license information, please see license.txt

from pydantic import BaseModel


class PortfolioSkill(BaseModel):
    name: str
    label: str
    relevance: str


class PortfolioAction(BaseModel):
    title: str
    description: str
    hours_invested: float
    category: str
    type: str
    skills: list[PortfolioSkill]


class UserPortfolio(BaseModel):
    first_name: str
    actions: list[PortfolioAction]
    total_hours_invested: float
    total_actions: int
