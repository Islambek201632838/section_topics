from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship

from config.shared_base import Base


class ScanResult(Base):
    __tablename__ = "scan_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vacancy_id = Column(String, ForeignKey("vacancies.vacancy_id"), nullable=False)
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    candidate_data = Column(JSON, nullable=False)

    # Relationships
    vacancy = relationship("Vacancy", back_populates="scan_results")
    resume = relationship("Resume", back_populates="scan_results")

    def __repr__(self):
        return f"<ScanResult(id={self.id}, vacancy_id={self.vacancy_id}, resume_id={self.resume_id})>"
