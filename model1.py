from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from config.shared_base import Base


# Resumes Table
class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    resume_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    last_name = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    middle_name = Column(String)
    title = Column(String)
    age = Column(Integer)
    salary_amount = Column(Float)
    salary_currency = Column(String)
    total_experience_months = Column(Integer)
    birth_date = Column(Date)
    driver_license_types = Column(String)
    resume_url = Column(String)
    platform_name = Column(String)
    response_date = Column(Date)
    vacancy_id = Column(Integer, ForeignKey("vacancies.vacancy_id"), nullable=False)

    # Relationships
    education = relationship("Education", back_populates="resume")
    experience = relationship("Experience", back_populates="resume")
    skills = relationship("Skill", back_populates="resume")
    contacts = relationship("Contact", back_populates="resume")
    vacancy = relationship("Vacancy", back_populates="resume")
    scan_results = relationship("ScanResult", back_populates="resume")
    languages = relationship("Language", back_populates="resume")
    citizenship = relationship("Citizenship", back_populates="resume")
    certificates = relationship("Certificate", back_populates="resume")


# Languages Table
class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    language_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    language_name = Column(String, nullable=False)
    language_level_id = Column(String)
    language_level_name = Column(String)

    # Relationship
    resume = relationship("Resume", back_populates="languages")


# Citizenship Table
class Citizenship(Base):
    __tablename__ = "citizenship"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    citizenship_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    country_id = Column(String)
    country_name = Column(String)

    # Relationship
    resume = relationship("Resume", back_populates="citizenship")


# Certificates Table
class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, autoincrement=True, unique=True)
    certificate_id = Column(String, primary_key=True, unique=True, nullable=False)
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    certificate_title = Column(String, nullable=False)
    certificate_url = Column(String)
    achieved_at = Column(Date)

    # Relationship
    resume = relationship("Resume", back_populates="certificates")



# Education Table
class Education(Base):
    __tablename__ = "education"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    education_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    level = Column(String)
    name = Column(String)
    organization = Column(String)
    result = Column(String)
    year = Column(Integer)

    # Relationship
    resume = relationship("Resume", back_populates="education")


# Experience Table
class Experience(Base):
    __tablename__ = "experience"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    experience_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    company = Column(String)
    position = Column(String)
    description = Column(Text)

    # Relationship
    resume = relationship("Resume", back_populates="experience")


# Skills Table
class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    skill_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    skill_name = Column(String, nullable=False)

    # Relationship
    resume = relationship("Resume", back_populates="skills")


# Contacts Table
class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, autoincrement=True, unique=True)  # Unique auto-incrementing ID
    contact_id = Column(String, primary_key=True, unique=True, nullable=False)  # String primary key
    resume_id = Column(String, ForeignKey("resumes.resume_id"), nullable=False)
    contact_type = Column(String)
    contact_info = Column(String)
    preferred = Column(String)

    # Relationship
    resume = relationship("Resume", back_populates="contacts")
