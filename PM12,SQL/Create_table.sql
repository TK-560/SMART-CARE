DROP TABLE IF EXISTS Appointments;
DROP TABLE IF EXISTS Patients;
DROP TABLE IF EXISTS Doctors;
DROP TABLE IF EXISTS Users;

CREATE TABLE Patients ( 
    PatientNumber CHAR(8) PRIMARY KEY,
    FirstName VARCHAR(50) NOT NULL, 
    LastName VARCHAR(50) NOT NULL, 
    IDNumber VARCHAR(13) NOT NULL UNIQUE, 
    DateOfBirth DATE NOT NULL, 
    Gender VARCHAR(20) NOT NULL, 
    ContactNumber VARCHAR(20) NOT NULL, 
    Email VARCHAR(100), 
    ResidentialAddress VARCHAR(255), 
    MedicalAidProvider VARCHAR(100), 
    MedicalAidNumber VARCHAR(50), 
    EmergencyContact VARCHAR(100), 
    RegistrationDate DATE NOT NULL, 
    CONSTRAINT CK_PatientNumber_Length 
        CHECK (LEN(PatientNumber) = 8) 
); 

CREATE TABLE Doctors (
    DoctorID INT IDENTITY(1,1) PRIMARY KEY, 
    FullName VARCHAR(100) NOT NULL, 
    Specialisation VARCHAR(100) NOT NULL, 
    PhoneNumber VARCHAR(20), 
    Email VARCHAR(100) 
); 

CREATE TABLE Appointments (
    AppointmentNumber INT IDENTITY(1,1) PRIMARY KEY, 
    AppointmentDate DATE NOT NULL, 
    AppointmentTime TIME NOT NULL, 
    DoctorID INT NOT NULL, 
    PatientNumber CHAR(8) NOT NULL, 
    AppointmentStatus VARCHAR(30) NOT NULL, 
    Notes VARCHAR(500), 
    CONSTRAINT FK_Appointment_Doctor 
        FOREIGN KEY (DoctorID) REFERENCES Doctors(DoctorID), 
    CONSTRAINT FK_Appointment_Patient 
        FOREIGN KEY (PatientNumber) REFERENCES Patients(PatientNumber) 
); 

CREATE TABLE Users (
    UserID INT IDENTITY(1,1) PRIMARY KEY, 
    Username VARCHAR(50) NOT NULL UNIQUE, 
    PasswordHash VARCHAR(255) NOT NULL 
);
