"""Tests for tabular file validators."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.validators.tabular import TabularFileRowCount, TabularFileValid


class TestTabularFileValid:
    """Tests for TabularFileValid validator."""

    def test_passes_for_valid_csv(self, tmp_path: Path) -> None:
        """Should pass for a valid CSV file."""
        csv_file = tmp_path / "valid.csv"
        csv_file.write_text("id,name,value\n1,foo,100\n2,bar,200\n")

        validator = TabularFileValid(str(csv_file))
        result = validator.check({})

        assert result.passed
        assert "3 columns" in result.message
        assert "2 rows" in result.message

    def test_passes_with_required_headers(self, tmp_path: Path) -> None:
        """Should pass when required headers are present."""
        csv_file = tmp_path / "headers.csv"
        csv_file.write_text("id,name,value,extra\n1,foo,100,x\n")

        validator = TabularFileValid(
            str(csv_file), required_headers=["id", "name", "value"]
        )
        result = validator.check({})

        assert result.passed

    def test_fails_with_missing_headers(self, tmp_path: Path) -> None:
        """Should fail when required headers are missing."""
        csv_file = tmp_path / "missing.csv"
        csv_file.write_text("id,value\n1,100\n")

        validator = TabularFileValid(
            str(csv_file), required_headers=["id", "name", "value"]
        )
        result = validator.check({})

        assert not result.passed
        assert "missing" in result.message.lower()
        assert "name" in str(result.details["missing"])

    def test_fails_with_insufficient_rows(self, tmp_path: Path) -> None:
        """Should fail when file has fewer rows than required."""
        csv_file = tmp_path / "few_rows.csv"
        csv_file.write_text("id,name\n1,foo\n")

        validator = TabularFileValid(str(csv_file), min_data_rows=5)
        result = validator.check({})

        assert not result.passed
        assert "not enough" in result.message.lower()

    def test_handles_empty_rows(self, tmp_path: Path) -> None:
        """Should not count empty rows as data."""
        csv_file = tmp_path / "empty_rows.csv"
        csv_file.write_text("id,name\n1,foo\n\n\n2,bar\n\n")

        validator = TabularFileValid(str(csv_file), min_data_rows=2)
        result = validator.check({})

        assert result.passed

    def test_handles_utf8_bom(self, tmp_path: Path) -> None:
        """Should handle UTF-8 BOM correctly."""
        csv_file = tmp_path / "bom.csv"
        content = "id,name\n1,foo\n"
        csv_file.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))

        validator = TabularFileValid(str(csv_file), required_headers=["id", "name"])
        result = validator.check({})

        assert result.passed

    def test_handles_latin1_encoding(self, tmp_path: Path) -> None:
        """Should fall back to latin-1 encoding."""
        csv_file = tmp_path / "latin1.csv"
        # Latin-1 specific character
        content = "id,name\n1,caf\xe9\n"
        csv_file.write_bytes(content.encode("latin-1"))

        validator = TabularFileValid(str(csv_file))
        result = validator.check({})

        assert result.passed

    def test_fails_for_missing_file(self, tmp_path: Path) -> None:
        """Should fail when file doesn't exist."""
        validator = TabularFileValid(str(tmp_path / "nonexistent.csv"))
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_for_unsupported_format(self, tmp_path: Path) -> None:
        """Should fail for unsupported file types."""
        json_file = tmp_path / "data.json"
        json_file.write_text('{"id": 1}')

        validator = TabularFileValid(str(json_file))
        result = validator.check({})

        assert not result.passed
        assert "unsupported" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        csv_file = tmp_path / "context.csv"
        csv_file.write_text("id\n1\n")

        validator = TabularFileValid("file_path", from_context=True)
        result = validator.check({"file_path": str(csv_file)})

        assert result.passed

    def test_invalid_min_data_rows(self) -> None:
        """Should raise ValueError for negative min_data_rows."""
        with pytest.raises(ValueError):
            TabularFileValid("test.csv", min_data_rows=-1)

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = TabularFileValid(
            "test.csv", required_headers=["id"], min_data_rows=5
        )
        assert "test.csv" in repr(validator)
        assert "required_headers" in repr(validator)
        assert "min_data_rows" in repr(validator)


class TestTabularFileValidExcel:
    """Tests for TabularFileValid with Excel files."""

    @pytest.fixture
    def sample_excel(self, tmp_path: Path) -> Path:
        """Create a sample Excel file."""
        import openpyxl

        xlsx_file = tmp_path / "sample.xlsx"
        wb = openpyxl.Workbook()

        # Default sheet
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["id", "name", "value"])
        ws.append([1, "foo", 100])
        ws.append([2, "bar", 200])

        # Second sheet
        ws2 = wb.create_sheet("Data")
        ws2.append(["col1", "col2"])
        ws2.append(["a", "b"])

        wb.save(xlsx_file)
        return xlsx_file

    def test_passes_for_valid_excel(self, sample_excel: Path) -> None:
        """Should pass for a valid Excel file."""
        validator = TabularFileValid(str(sample_excel))
        result = validator.check({})

        assert result.passed
        assert "3 columns" in result.message
        assert "2 rows" in result.message

    def test_passes_with_sheet_name(self, sample_excel: Path) -> None:
        """Should read from named sheet."""
        validator = TabularFileValid(
            str(sample_excel),
            sheet_name="Data",
            required_headers=["col1", "col2"],
        )
        result = validator.check({})

        assert result.passed

    def test_passes_with_sheet_index(self, sample_excel: Path) -> None:
        """Should read from sheet by index."""
        validator = TabularFileValid(str(sample_excel), sheet_name=1)
        result = validator.check({})

        assert result.passed

    def test_fails_for_missing_sheet(self, sample_excel: Path) -> None:
        """Should fail when sheet doesn't exist."""
        validator = TabularFileValid(str(sample_excel), sheet_name="NonExistent")
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_fails_for_sheet_index_out_of_range(self, sample_excel: Path) -> None:
        """Should fail when sheet index is out of range."""
        validator = TabularFileValid(str(sample_excel), sheet_name=99)
        result = validator.check({})

        assert not result.passed
        assert "out of range" in result.message.lower()


class TestTabularFileRowCount:
    """Tests for TabularFileRowCount validator."""

    def test_passes_when_count_in_range(self, tmp_path: Path) -> None:
        """Should pass when row count is within range."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n2\n3\n4\n5\n")

        validator = TabularFileRowCount(str(csv_file), min_rows=3, max_rows=10)
        result = validator.check({})

        assert result.passed
        assert "5" in result.message

    def test_fails_when_too_few_rows(self, tmp_path: Path) -> None:
        """Should fail when row count is below minimum."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n2\n")

        validator = TabularFileRowCount(str(csv_file), min_rows=5)
        result = validator.check({})

        assert not result.passed
        assert "too few" in result.message.lower()

    def test_fails_when_too_many_rows(self, tmp_path: Path) -> None:
        """Should fail when row count is above maximum."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n" + "\n".join(str(i) for i in range(100)) + "\n")

        validator = TabularFileRowCount(str(csv_file), max_rows=10)
        result = validator.check({})

        assert not result.passed
        assert "too many" in result.message.lower()

    def test_passes_with_min_only(self, tmp_path: Path) -> None:
        """Should pass when only min_rows is set and met."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n2\n3\n")

        validator = TabularFileRowCount(str(csv_file), min_rows=2)
        result = validator.check({})

        assert result.passed

    def test_passes_with_max_only(self, tmp_path: Path) -> None:
        """Should pass when only max_rows is set and not exceeded."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n2\n")

        validator = TabularFileRowCount(str(csv_file), max_rows=10)
        result = validator.check({})

        assert result.passed

    def test_fails_for_missing_file(self, tmp_path: Path) -> None:
        """Should fail when file doesn't exist."""
        validator = TabularFileRowCount(str(tmp_path / "nonexistent.csv"))
        result = validator.check({})

        assert not result.passed
        assert "not found" in result.message.lower()

    def test_from_context(self, tmp_path: Path) -> None:
        """Should read path from context when from_context is True."""
        csv_file = tmp_path / "context.csv"
        csv_file.write_text("id\n1\n2\n3\n")

        validator = TabularFileRowCount("file_path", min_rows=2, from_context=True)
        result = validator.check({"file_path": str(csv_file)})

        assert result.passed

    def test_invalid_min_rows(self) -> None:
        """Should raise ValueError for negative min_rows."""
        with pytest.raises(ValueError):
            TabularFileRowCount("test.csv", min_rows=-1)

    def test_invalid_max_less_than_min(self) -> None:
        """Should raise ValueError when max_rows < min_rows."""
        with pytest.raises(ValueError):
            TabularFileRowCount("test.csv", min_rows=10, max_rows=5)

    def test_repr(self) -> None:
        """Should have correct string representation."""
        validator = TabularFileRowCount("test.csv", min_rows=10, max_rows=100)
        assert "test.csv" in repr(validator)
        assert "min_rows" in repr(validator)
        assert "max_rows" in repr(validator)
