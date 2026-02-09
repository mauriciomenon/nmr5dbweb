#!/bin/bash

# Manual benchmark of converter implementations (runs from repo root)

echo "==================================="
echo "MDB2SQL Manual Benchmark Test"
echo "==================================="
echo ""

TEST_FILE="import_folder/DB2_20_11_2013.mdb"
OUTPUT_DIR="artifacts"
OUTPUT_DB_BASENAME="benchmark_test.duckdb"
OUTPUT_DB="${OUTPUT_DIR}/${OUTPUT_DB_BASENAME}"

mkdir -p "$OUTPUT_DIR"
rm -f "${OUTPUT_DB}" "${OUTPUT_DB}"_*

echo "Test file: $TEST_FILE"
echo "Output DB (base): $OUTPUT_DB_BASENAME (stored in $OUTPUT_DIR)"
echo ""

echo "-----------------------------------"
echo "Testing MDBTOOLS implementation"
echo "-----------------------------------"
START=$(date +%s)
python3 converters/convert_mdbtools.py --input "$TEST_FILE" --output "${OUTPUT_DB}_mdbtools" 2>&1 | tail -5
END=$(date +%s)
MDBTOOLS_TIME=$((END - START))
echo "Time: ${MDBTOOLS_TIME}s"
echo ""

echo "-----------------------------------"
echo "Testing JACKCESS implementation"
echo "-----------------------------------"
START=$(date +%s)
python3 converters/convert_jackcess.py --input "$TEST_FILE" --output "${OUTPUT_DB}_jackcess" 2>&1 | tail -5
END=$(date +%s)
JACKCESS_TIME=$((END - START))
echo "Time: ${JACKCESS_TIME}s"
echo ""

echo "-----------------------------------"
echo "Testing PYPYODBC implementation"
echo "-----------------------------------"
START=$(date +%s)
python3 converters/convert_pyodbc.py --input "$TEST_FILE" --output "${OUTPUT_DB}_pyodbc" 2>&1 | tail -5
END=$(date +%s)
PYODBC_TIME=$((END - START))
echo "Time: ${PYODBC_TIME}s"
echo ""

echo "==================================="
echo "SUMMARY"
echo "==================================="
echo "MDBTOOLS: ${MDBTOOLS_TIME}s"
echo "JACKCESS:  ${JACKCESS_TIME}s"
echo "PYPYODBC:  ${PYODBC_TIME}s"
echo "==================================="

ls -lh "${OUTPUT_DIR}"/*_mdbtools "${OUTPUT_DIR}"/*_jackcess "${OUTPUT_DIR}"/*_pyodbc 2>/dev/null
