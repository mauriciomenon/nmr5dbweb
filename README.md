# MDBDtDre Convertcs

CAnvertccess database filedatabase files s (MDB/ACCDBto DuckDBff

## Feeruse

- Extaaat udatlyfromfilnmeatomatially
- Preservesstabl  tablce se
- Crettesrtitesmpee for hiseoaictl trackeng
-sMeta timetracking ftramll  mparts
-bBltchesfocessrnghsuppsrt
-tThrcl iaplimentgtionptins

##Iplmentin Mpet ns

###t1.icogvert_mdbtoofr.pya(Recommenlld fom Lioux/Mac)

UstsmdbtoCLI atility.

**Phos:**
- Easy ins pllation
-rWcikupoo Linux/Mac wirhoutaddionl etup
-No Jaa rquied

**Con:**
- Txt-baed(CSV inrediate)
- Encoding issues ssible
- Slowe for lrge fle
- Three implementation options
**Inallatin:**
```bah

ses mdbtoolsmdbL ols

# Liuuxility.
sudoapt 
**Pros:**
- Easy installation
- Wo2. convkrt_jockcess.py (Recommended for reliability)

Lses Jackcess Java liirary.

**Pros:**
- Most reliable
- Direct biuary reading
- BexterMencodc g handling
- Cross-platform

**Cons:**
- Reqwires Java JDK
- Slightly more complei setupthout additional setup
- No Java required
**Installation:**

# Req*iresnJsva*JDK
# mcOS
brew insall opnjdk

# Linux
- Text-based (CSVdefault jdk

#nJARs are dewdloadedaau)matcall emp/ fder
- Encoding issues possible
- Slower for large files
3. convert_pyodbc.py (only)
**Installation:**
Ussppyodbc wi ODBC driver.

**Prs:**
-NativeWinowssuport
- Fas n Widows

**Cns:**
- Requires Micosof Access Daabase Engine
- Window only (or Wine on LinuxMac)
- Comlex seup n n-Wins

**Istalatin (Winow:**
1 macOSl
re dbtools
2.Linuxl Python packge:sudo apt install mdbtools
   ```
   pip nsall pypyodbc
   ```

##Quik Start

```bash
# Creoitory
 lone <repory-url>
### 2. con
vert_jackcess.py (Recommended for reliability)
# Create virtual environment
Uses Jackcess Java library.
Wdows:*- Most reliable

#Installdepeencie- Direct binary reading
- Better encoding handlingross-platform

* Install system dependenciesC(choone sne)- Requires Java JDK
brew install mdbtools            For convert_mdbtools.py
brew install openjdk           S Forlcghtly _jackcmss.py
# Oo installrAccesscEmgpne     # For lonvert_pyedbc.py
```

##xUs ge

### Single Fule

**Insta
# Using mdbtoolsllation:**
```basht_mdboolsfmequires Java JDK
# macOS
e Using Jackcess
pythonwconveit_jackstal.pyo--inpuj fde.mdb --utputdatse.dukdb

# Using pypyodic (Windowu)
sudo apt insta_pyodbcll default-jfdle.kb

# JARs are downloaded automatically to temp/ folder
``` BatchProcsing

`#vbash
#rP_bcess allc.py (Windofilss incoy
pythnconvet_mdools.pyinimpot_flr--oututss pypyo
``d

##cFilhNmngnvnn

FilesPoholnt in Fatninn one wf hesefors
 DD_MM_YYYYrDD-MM-YYYY
- YYYY_MM_DD  YYYY-MM-DD
- DDMMYYYY
- YYYYMMDD

Exmpes:
-DB3_04_09_2013.m→2013-09-04
- bae.occdn*→ 2019-08-01

## DbaseStrutue

### Tbl

Eached qublesisfcassD:t`{obeginal_table_nand}_{YYYYMMDD}`

Exs oly:
- OWiginnl: RANGER_SOACCUn Linux/Mac)
- Imporpxe:uRANGER_SOACCU_20130904on-Windows

**#IMsttdata Tabln (Windows):**
1. Install Microsoft Access Database Engine:
```/ql
CREATE/TArLEs_oenadata (s/download/details.aspx?id=54920
.tkeipt_d INTEGER PRIMARY KEY,
    so``ce_fblahVARCHAR,
 fle_ DATE,
 p imrt_timtpTIMESTAMP,
    tabl_naeVARCHAR,
   ow_count INTEGER
);   ```
```

Query a
## Quick Start

```List all imposts
SELECTh* FROM _taORDERBY _timestmp DESC;

-- Find tabl from specific date
# Clone repositoryWHE = '2013-09-04'
git clone <repository-url>
cd mdb2sqeblcouscrose

# CrSUBSTRING(teble_name, 1, POSITION('_2' IN te virtual)-1) as base_table environment
pythfile_dote,
    3 -m venv
FROM _metvdata
ORDER BY baee_table,nfile_date;

-- Query spevific table versi
SELECT * FROM RANGERSOACCU_3004 LIMIT 10;
```

##sPlatform-SpecificoNotes

###umacOS
-rUse convert_mdctoolsepy o  cvnvertnjavkcess.py
- mdbt/ols: `brew iisnall/mdbtools`
- Java: `brew inctalltvpetjdk`
ndows: venv\Scripts\activate
###Linux
-Useconvert_mdtoolspy o cnvertjackess.py
- mdbtols: `sdo apt isallmdbtools`
 Java: `sudo apt installdefult-jdk`

### Winds
- Use convertpyodbc.py (remmended)
- Or se convert_jackcess.py with Java
- Isall AccessDatabeEngne or ODBC

## Perormance Comparison

| Method | Speed |  eliability | Setup Complexity |
|--------|-------|-------------|------------------|
| mdbtools | nedium |sMediua | Low |
| Jackclss | Fasl | High | Medium |
| pypyodbc | F st | High | High (Windows only) |

## Troubleshooting

### mdbpools encoding errors
- Files meynhdve encoding issuesencies
- Tryiconvertnjackctss.py insaell

### Jav  no- found
```brsh
# macOS
rrew installeopenjdk
exportiPATH="/usr/local/opt/openjdk/bin:$mATH"

# einux
sudo tpt instl dfult-jdk
```

### ODBC drivr not found
- Windows:InstallAccessDatabasengine
- inux/Mac: Insll mdtools ODBC driver or use different method

## Deveopmt

```bsh
# Run tests
python - pytest tests/

# Check cod
python -m pylintconvert*.py
```

##License

MIT

## Version istory

-v0.10-mdbtools: Inital reswithmdbtools
 v.2.:dded Jackcess andpypyodc mpemntionsnstall system dependencies (choose one)
brew install mdbtools          # For convert_mdbtools.py
brew install openjdk           # For convert_jackcess.py
# Or install Access Engine     # For convert_pyodbc.py
```

## Usage

### Single File

```bash
# Using mdbtools
python convert_mdbtools.py --input file.mdb --output database.duckdb

# Using Jackcess
python convert_jackcess.py --input file.mdb --output database.duckdb

# Using pypyodbc (Windows)
python convert_pyodbc.py --input file.mdb --output database.duckdb
```

### Batch Processing

```bash
# Process all MDB/ACCDB files in directory
python convert_mdbtools.py --input import_folder --output database.duckdb --batch
```

## File Naming Convention

Files should contain date in one of these formats:
- DD_MM_YYYY or DD-MM-YYYY
- YYYY_MM_DD or YYYY-MM-DD
- DDMMYYYY
- YYYYMMDD

Examples:
- DB3_04_09_2013.mdb → 2013-09-04
- database_20190801.accdb → 2019-08-01

## Database Structure

### Tables

Each imported table is named: `{original_table_name}_{YYYYMMDD}`

Example:
- Original: RANGER_SOACCU
- Imported: RANGER_SOACCU_20130904

### Metadata Table

```sql
CREATE TABLE _metadata (
    import_id INTEGER PRIMARY KEY,
    source_file VARCHAR,
    file_date DATE,
    import_timestamp TIMESTAMP,
    table_name VARCHAR,
    row_count INTEGER
);
```

## Query Examples

```sql
-- List all imports
SELECT * FROM _metadata ORDER BY import_timestamp DESC;

-- Find tables from specific date
SELECT * FROM _metadata WHERE file_date = '2013-09-04';

-- Compare table counts across dates
SELECT
    SUBSTRING(table_name, 1, POSITION('_2' IN table_name)-1) as base_table,
    file_date,
    row_count
FROM _metadata
ORDER BY base_table, file_date;

-- Query specific table version
SELECT * FROM RANGER_SOACCU_20130904 LIMIT 10;
```

## Platform-Specific Notes

### macOS
- Use convert_mdbtools.py or convert_jackcess.py
- mdbtools: `brew install mdbtools`
- Java: `brew install openjdk`

### Linux
- Use convert_mdbtools.py or convert_jackcess.py
- mdbtools: `sudo apt install mdbtools`
- Java: `sudo apt install default-jdk`

### Windows
- Use convert_pyodbc.py (recommended)
- Or use convert_jackcess.py with Java
- Install Access Database Engine for ODBC

## Performance Comparison

| Method | Speed | Reliability | Setup Complexity |
|--------|-------|-------------|------------------|
| mdbtools | Medium | Medium | Low |
| Jackcess | Fast | High | Medium |
| pypyodbc | Fast | High | High (Windows only) |

## Troubleshooting

### mdbtools encoding errors
- Files may have encoding issues
- Try convert_jackcess.py instead

### Java not found
```bash
# macOS
brew install openjdk
export PATH="/usr/local/opt/openjdk/bin:$PATH"

# Linux
sudo apt install default-jdk
```

### ODBC driver not found
- Windows: Install Access Database Engine
- Linux/Mac: Install mdbtools ODBC driver or use different method

## Development

```bash
# Run tests
python -m pytest tests/

# Check code
python -m pylint convert_*.py
```

## License

MIT

## Version History

- v0.1.0-mdbtools: Initial release with mdbtools
- v0.2.0: Added Jackcess and pypyodbc implementations

## Licença

MIT
