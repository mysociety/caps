from os.path import join, basename, splitext, isfile
import os

DATA_DIR = 'data'
DB_NAME = 'plans.db'
DB = join(DATA_DIR, DB_NAME)
PROCESSED_CSV_NAME = 'plans.csv'
PROCESSED_CSV = join(DATA_DIR, PROCESSED_CSV_NAME)


def convert_csv_to_sqlite():
    if os.path.isfile(DB):
        os.remove(DB)
    os.system(f"csvs-to-sqlite {PROCESSED_CSV} {DB} -f text")

print("converting to sqlite")
convert_csv_to_sqlite()
