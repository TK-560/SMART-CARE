import pyodbc


def get_connection():
    try:
        return pyodbc.connect(
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=TK;"
            "DATABASE=SmartCareDB;"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    except pyodbc.Error as e:
        print("Could not connect", e)
    return None


"""
client = get_connection()


def insert_new_patient_number():
    cursor = client.cursor()
    cursor.execute('')
"""
