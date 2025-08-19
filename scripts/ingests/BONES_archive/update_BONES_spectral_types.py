import logging
from astropy.io import ascii

from astrodb_utils import load_astrodb
from astrodb_utils.sources import (
    AstroDBError,
    find_publication,
)
from astrodb_utils.publications import(
    ingest_publication
)
import sys
sys.path.append(".")
from simple import REFERENCE_TABLES
from simple.utils.spectral_types import ingest_spectral_type

astrodb_utils_logger = logging.getLogger("astrodb_utils")
logger = logging.getLogger(
    "astrodb_utils.bones_sptypes"
)  # Sets up a child of the "astrodb_utils" logger

logger.setLevel(logging.INFO)  # Set logger to INFO/DEBUG/WARNING/ERROR/CRITICAL level
astrodb_utils_logger.setLevel(logging.INFO)

DB_SAVE = False
RECREATE_DB = True

SCHEMA_PATH = "simple/schema.yaml"
db = load_astrodb(
    "SIMPLE.sqlite",
    recreatedb=RECREATE_DB,
    reference_tables=REFERENCE_TABLES,
    felis_schema=SCHEMA_PATH,
)

link = (
    "scripts/ingests/bones_archive/updated_BONES_data.csv"
)

# read the csv data into an astropy table
bones_sheet_table = ascii.read(
    link,
    format="csv",
    data_start=1,
    header_start=0,
    guess=False,
    fast_reader=False,
    delimiter=",",
)

updated = 0
skipped = 0
already_exists = 0
pub_ingested=0

# helper method for extracting ads key from link
def extractADS(link):
    ads = ""
    if 'harvard.edu' in link:
        start = link.find('abs/')+4
        end = link.find('/abstract')
        ads = link[start:end]
        ads = ads.replace("%26", "&")
    return ads

def update_ref(db, source, ref):
    spectral_type_search = db.search_object(
        name = source,

        output_table="SpectralTypes"
    )
    if len(spectral_type_search) > 0:
        for spt in spectral_type_search:
            if spt["comments"] == "From the BONES archive":
                spt["reference"] = ref
    return

for source in bones_sheet_table:
    bones_name = source["NAME"].replace("\u2212", "-")
    bones_name = bones_name.replace("\u2212", "-")
    bones_name = bones_name.replace("\u2013", "-")
    bones_name = bones_name.replace("\2014", "-")
    bones_spectra = source["LIT_SPT"]

    try:
        spt_ads = extractADS(source["Spt Bibcode"])
        spt_ref = find_publication(db=db, bibcode = spt_ads)

        if spt_ref[0] is False:
            try:
                ingest_publication(db = db, bibcode = spt_ads)
                pub_ingested += 1
                ref = find_publication(db=db, bibcode=spt_ads)
            except Exception as e:
                logger.error("Find and ingest pattern didn't work" + spt_ads)
                raise e
            
        #if the spectral type reference is updated in the new csv file, update the JSON file
        update_ref(db=db, source = bones_name, ref = spt_ref)
        updated += 1
    except AstroDBError as e:
        msg = "ingest failed with error: " + str(e)
        logger.warning(msg)
        if "Spectral type already in the database" in str(e):
            already_exists+=1
        else:
            skipped += 1
            raise e


total = len(bones_sheet_table)
logger.info(f"skipped: {skipped}")  # 0 skipped
logger.info(f"spectra_ingested: {updated}")  # 199 updated
logger.info(f"Already exists: {already_exists}") # 10 already exists in database
logger.info(f"Publications ingested: {pub_ingested}") #7 new publications ingested
logger.info(f"total: {total}")  # 209 total
if DB_SAVE:
    db.save_database(directory="data/")
