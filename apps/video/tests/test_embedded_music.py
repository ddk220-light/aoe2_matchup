import struct
import pytest
from extract_intro_music import embedded_media


def bank(offset=0):
    index = struct.pack('<III', 12345, offset, 8)
    return b'DIDX' + struct.pack('<I', len(index)) + index + b'DATA' + struct.pack('<I', 8) + b'RIFFtest'


def test_exact_media_id_is_resolved():
    assert embedded_media(bank(), 12345) == b'RIFFtest'
    assert embedded_media(bank(), 12346) is None


def test_invalid_byte_range_is_rejected():
    with pytest.raises(ValueError, match='outside DATA'):
        embedded_media(bank(offset=1), 12345)
