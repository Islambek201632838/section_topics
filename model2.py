from sqlalchemy import Column, Integer, Text, String, Boolean
from sqlalchemy.orm import relationship

from config.shared_base import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    id = Column(Integer, unique=True, autoincrement=True)
    vacancy_id = Column(String, primary_key=True, unique=True, nullable=False)
    description = Column(Text, nullable=False)
    responses = Column(Integer, default=0)
    active = Column(Boolean, default=False)
    # Relationships
    resume = relationship("Resume", back_populates="vacancy")
    scan_results = relationship("ScanResult", back_populates="vacancy")  # Add this relationship

    def __repr__(self):
        return f"<Vacancy(vacancy_id={self.vacancy_id}, description={self.description[:30]}, responses={self.responses})>"
