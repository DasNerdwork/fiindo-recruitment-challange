""" Database models for the Fiindo recruitment challenge. """

from sqlalchemy import Column, String, Text, DateTime, JSON, Float
from sqlalchemy.sql import func
from app.database import Base


class RawGeneralData(Base):
    __tablename__ = "raw_general_data"

    symbol = Column(String, primary_key=True)
    industry = Column(String, index=True)
    general_data = Column(JSON)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class RawFinancialData(Base):
    __tablename__ = "raw_financial_data"

    symbol = Column(String, primary_key=True)
    income_data = Column(JSON)
    balance_data = Column(JSON)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

class TickerStatistics(Base):
    __tablename__ = "ticker_statistics"

    symbol = Column(String, primary_key=True)
    pe_ratio = Column(Float, nullable=True)
    revenue_growth = Column(Float, nullable=True)
    net_income_ttm = Column(Float, nullable=True)
    debt_ratio = Column(Float, nullable=True)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())

class IndustryStatistics(Base):
    __tablename__ = "industry_statistics"

    industry = Column(String, primary_key=True)
    avg_pe_ratio = Column(Float)
    avg_revenue_growth = Column(Float)
    sum_revenue = Column(Float)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
