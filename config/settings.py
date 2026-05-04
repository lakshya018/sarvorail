"""
Application settings and configurations.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()



# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Scraper Settings
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

MAJOR_JUNCTIONS = [
    "NDLS", "BCT", "MAS", "HWH", "PUNE", "ADI", "JP", "BPL", "LKO", 
    "CSTM", "SBC", "SC", "NZM", "UDZ", "AII", "AGC", "GWL", "JHS", "CNB", "PRYJ",
    "BSB", "MGS", "GAYA", "PNBE", "DNR", "MFP", "SPJ", "BJU", "RXL", "DBG",
    "GKP", "ASR", "LDH", "CDG", "UMB", "SRE", "DDN", "HW", "MB", "BE",
    "GZB", "DLI", "DEC", "RE", "AWR", "BKI", "BTE", "MTJ", "AF", "TDL",
    "ET", "KTE", "STA", "MKP", "JU", "BKN", "FL", "KOTA", "RTM", "NAD",
    "UJN", "INDB", "BRC", "ST", "BSR", "KYN", "KOP", "MRJ", "UBL", "MAO",
    "MAQ", "ERS", "TVC", "ED", "CBE", "TPJ", "MDU", "TEN", "RU", "BZA",
    "VSKP", "BBS", "CTC", "KGP", "TATA", "RNC", "DHN", "ASN", "MLDT", "NJP",
    "GHY", "LMG", "DBRG"
]
