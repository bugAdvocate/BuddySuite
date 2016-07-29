import pytest
from unittest import mock
from urllib.error import HTTPError, URLError
from collections import OrderedDict
import sys
import tempfile
import re
import json
from ... import buddy_resources as br
from ... import DatabaseBuddy as Db


def patched_close(self):  # This suppresses an 'ignored' exception
    if not self.close_called:
        self.close_called = True
        if type(self.file) == str:
            pass
        else:
            self.file.close()
tempfile._TemporaryFileCloser.close = patched_close

# A few real accession numbers to test things out with
ACCNS = ["NP_001287575.1", "ADH10263.1", "XP_005165403.2", "A0A087WX72", "A0A096MTH0", "A0A0A9YFB0",
         "XM_003978475", "ENSAMEG00000011912", "ENSCJAG00000008732", "ENSMEUG00000000523"]


# Mock functions and classes
def mock_urlopen_handle_uniprot_ids(*args, **kwargs):
    print("mock_urlopen_handle_uniprot_ids\nargs: %s\nkwargs: %s" % (args, kwargs))
    tmp_file = br.TempFile(byte_mode=True)
    tmp_file.write('''A8XEF9
O61786
A0A0H5SBJ0
'''.encode("utf-8"))
    return tmp_file.get_handle("r")


def mock_urlopen_uniprot_count_hits(*args, **kwargs):
    print("mock_urlopen_uniprot_count_hits\nargs: %s\nkwargs: %s" % (args, kwargs))
    tmp_file = br.TempFile(byte_mode=True)
    tmp_file.write('''# Search: (inx15)+OR+(inx16)
O61787
A0A0V1AZ11
A8XEF9
A8XEF8
A0A0B2VB60
A0A0V0W5E2
O61786
A0A0H5SBJ0
E3MGD6
E3MGD5
//'''.encode("utf-8"))
    return tmp_file.get_handle("r")


def mock_urlopen_uniprot_summary(*args, **kwargs):
    print("mock_urlopen_uniprot_summary\nargs: %s\nkwargs: %s" % (args, kwargs))
    tmp_file = br.TempFile(byte_mode=True)
    tmp_file.write('''# Search: inx15
A8XEF9	A8XEF9_CAEBR	381	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
O61786	O61786_CAEEL	382	6239	Caenorhabditis elegans	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0H5SBJ0	A0A0H5SBJ0_BRUMA	129	6279	Brugia malayi (Filarial nematode worm)	Innexin	Function (1); Sequence similarities (1); Subcellular location (1)
E3MGD6	E3MGD6_CAERE	384	31234	Caenorhabditis remanei (Caenorhabditis vulgaris)	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
//
# Search: inx16
O61787	INX16_CAEEL	372	6239	Caenorhabditis elegans	Innexin-16 (Protein opu-16)	Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V1AZ11	A0A0V1AZ11_TRISP	406	6334	Trichinella spiralis (Trichina worm)	Innexin	Caution (1); Function (1); Sequence similarities (1); Subcellular location (2)
A8XEF8	A8XEF8_CAEBR	374	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0B2VB60	A0A0B2VB60_TOXCA	366	6265	Toxocara canis (Canine roundworm)	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V0W5E2	A0A0V0W5E2_9BILA	410	92179	Trichinella sp. T6	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
//'''.encode("utf-8"))
    return tmp_file.get_handle("r")


def mock_urlopen_raise_httperror(*args, **kwargs):
    print("mock_urlopen_raise_httperror\nargs: %s\nkwargs: %s" % (args, kwargs))
    raise HTTPError(url="http://fake.come", code=101, msg="Fake HTTPError from Mock", hdrs="Foo", fp="Bar")


def mock_urlopen_raise_503_httperror(*args, **kwargs):
    print("mock_urlopen_raise_httperror\nargs: %s\nkwargs: %s" % (args, kwargs))
    raise HTTPError(url="http://fake.come", code=503, msg="Service unavailable", hdrs="Foo", fp="Bar")


def mock_urlopen_raise_urlerror(*args, **kwargs):
    print("mock_urlopen_raise_urlerror\nargs: %s\nkwargs: %s" % (args, kwargs))
    raise URLError("Fake URLError from Mock")


def mock_urlopen_raise_urlerror_8(*args, **kwargs):
    print("mock_urlopen_raise_urlerror\nargs: %s\nkwargs: %s" % (args, kwargs))
    raise URLError("Fake URLError from Mock: Errno 8")


def mock_urlopen_raise_keyboardinterrupt(*args, **kwargs):
    print("mock_urlopen_raise_keyboardinterrupt\nargs: %s\nkwargs: %s" % (args, kwargs))
    raise KeyboardInterrupt()


# ################################################# Database Clients ################################################# #
# Generic
def test_client_init():
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[3:6]))
    client = Db.GenericClient(dbbuddy)
    assert hash(dbbuddy) == hash(client.dbbuddy)
    assert type(client.http_errors_file) == br.TempFile
    assert type(client.results_file) == br.TempFile
    assert client.max_url == 1000
    with client.lock:
        assert True


def test_client_parse_error_file():
    dbbuddy = Db.DbBuddy()
    client = Db.GenericClient(dbbuddy)

    assert not client.parse_error_file()
    assert not dbbuddy.failures
    client.http_errors_file.write("Casp9\n%s\n//\n" % HTTPError("101", "Fake HTTPError from Mock", "Foo", "Bar", "Baz"))
    client.http_errors_file.write("Inx1\n%s\n//\n" % URLError("Fake URLError from Mock"))

    assert client.parse_error_file() == '''Casp9
HTTP Error Fake HTTPError from Mock: Foo

Inx1
<urlopen error Fake URLError from Mock>

'''
    assert len(dbbuddy.failures) == 2

    # Repeat to make sure that the same error is not added again
    client.http_errors_file.write("Inx1\n%s\n//\n" % URLError("Fake URLError from Mock"))
    assert not client.parse_error_file()
    assert len(dbbuddy.failures) == 2


def test_client_split_for_url():
    dbbuddy = Db.DbBuddy()
    client = Db.GenericClient(dbbuddy, max_url=40)
    assert client.group_terms_for_url(ACCNS) == ['NP_001287575.1,ADH10263.1', 'XP_005165403.2,A0A087WX72,A0A096MTH0',
                                                 'A0A0A9YFB0,XM_003978475', 'ENSAMEG00000011912,ENSCJAG00000008732',
                                                 'ENSMEUG00000000523']
    client = Db.GenericClient(dbbuddy, max_url=10)
    with pytest.raises(ValueError) as err:
        client.group_terms_for_url(ACCNS)
    assert "The provided accession or search term is too long (>10)." in str(err)


# UniProt
def test_uniprotrestclient_init():
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[3:6]))
    client = Db.UniProtRestClient(dbbuddy)
    assert hash(dbbuddy) == hash(client.dbbuddy)
    assert client.server == 'http://www.uniprot.org/uniprot'
    assert type(client.http_errors_file) == br.TempFile
    assert type(client.results_file) == br.TempFile
    assert client.max_url == 1000


def test_uniprotrestclient_query_uniprot(capsys):
    dbbuddy = Db.DbBuddy()
    client = Db.UniProtRestClient(dbbuddy)
    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_handle_uniprot_ids):
        client.query_uniprot("inx15", {"format": "list"})

    assert client.results_file.read() == '''# Search: inx15
A8XEF9
O61786
A0A0H5SBJ0
//
'''
    # Also make sure request_params can come in as a list
    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_handle_uniprot_ids):
        client.query_uniprot("inx15", [{"format": "list"}])

    # Errors
    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_raise_httperror):
        client.query_uniprot("inx15", [{"format": "list"}])
    assert client.http_errors_file.read() == "Uniprot search failed for 'inx15'\nHTTP Error 101: " \
                                             "Fake HTTPError from Mock\n//\n"

    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_raise_urlerror):
        client.query_uniprot("inx15", [{"format": "list"}])
    assert "<urlopen error Fake URLError from Mock>" in client.http_errors_file.read()

    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_raise_keyboardinterrupt):
        client.query_uniprot("inx15", [{"format": "list"}])
    out, err = capsys.readouterr()
    assert "\n\tUniProt query interrupted by user\n" in err

    params = {"format": "tab", "columns": "id,entry name,length,organism-id,organism,protein names,comments"}
    client.query_uniprot("ABXEF9", params)


def test_uniprotrestclient_count_hits():
    dbbuddy = Db.DbBuddy("inx15,inx16")
    client = Db.UniProtRestClient(dbbuddy)
    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_uniprot_count_hits):
        assert client.count_hits() == 10

        for indx in range(10):
            client.dbbuddy.search_terms.append("a" * 110)
        assert client.count_hits() == 20

    with mock.patch('buddysuite.DatabaseBuddy.urlopen', mock_urlopen_raise_httperror):
        assert client.count_hits() == 0
        assert "d3b8e6bb4b9094117b7555b01dc85f64" in client.dbbuddy.failures

    with pytest.raises(ValueError) as err:
        client.dbbuddy.search_terms[0] = "a" * 1001
        client.count_hits()
    assert "Search term exceeds size limit of 1000 characters." in str(err)


def test_uniprotrestclient_search_proteins(monkeypatch, capsys):
    def patch_query_uniprot_multi(*args, **kwargs):
        print("patch_query_uniprot_multi\nargs: %s\nkwargs: %s" % (args, kwargs))
        client1.results_file.write('''# Search: inx15
A8XEF9	A8XEF9_CAEBR	381	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
O61786	O61786_CAEEL	382	6239	Caenorhabditis elegans	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0H5SBJ0	A0A0H5SBJ0_BRUMA	129	6279	Brugia malayi (Filarial nematode worm)	Innexin	Function (1); Sequence similarities (1); Subcellular location (1)
E3MGD6	E3MGD6_CAERE	384	31234	Caenorhabditis remanei (Caenorhabditis vulgaris)	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
//
# Search: inx16
O61787	INX16_CAEEL	372	6239	Caenorhabditis elegans	Innexin-16 (Protein opu-16)	Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V1AZ11	A0A0V1AZ11_TRISP	406	6334	Trichinella spiralis (Trichina worm)	Innexin	Caution (1); Function (1); Sequence similarities (1); Subcellular location (2)
A8XEF8	A8XEF8_CAEBR	374	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0B2VB60	A0A0B2VB60_TOXCA	366	6265	Toxocara canis (Canine roundworm)	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V0W5E2	A0A0V0W5E2_9BILA	410	92179	Trichinella sp. T6	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
//''', "w")
        return

    def patch_query_uniprot_single(*args, **kwargs):
        print("patch_query_uniprot_single\nargs: %s\nkwargs: %s" % (args, kwargs))
        client2.results_file.write('''# Search: inx15
A8XEF9	A8XEF9_CAEBR	381	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
O61786	O61786_CAEEL	382	6239	Caenorhabditis elegans	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0H5SBJ0	A0A0H5SBJ0_BRUMA	129	6279	Brugia malayi (Filarial nematode worm)	Innexin
E3MGD6	E3MGD6_CAERE	384	31234	Caenorhabditis remanei (Caenorhabditis vulgaris)	Innexin
//''', "w")
        return

    monkeypatch.setattr(Db.UniProtRestClient, "count_hits", lambda _: 0)
    dbbuddy = Db.DbBuddy("inx15,inx16")
    client1 = Db.UniProtRestClient(dbbuddy)
    client1.search_proteins()
    out, err = capsys.readouterr()
    assert "Uniprot returned no results\n\n" in err

    monkeypatch.setattr(Db.UniProtRestClient, "count_hits", lambda _: 9)
    monkeypatch.setattr(br, "run_multicore_function", patch_query_uniprot_multi)
    client1.search_proteins()
    out, err = capsys.readouterr()
    assert "Retrieving summary data for 9 records from UniProt\n" in err
    assert "Querying UniProt with 2 search terms (Ctrl+c to abort)\n" in err
    assert len(dbbuddy.records) == 9

    monkeypatch.setattr(Db.UniProtRestClient, "query_uniprot", patch_query_uniprot_single)
    dbbuddy = Db.DbBuddy("inx15")
    client2 = Db.UniProtRestClient(dbbuddy)
    client2.search_proteins()
    out, err = capsys.readouterr()
    assert "Querying UniProt with the search term 'inx15'...\n" in err
    assert len(dbbuddy.records) == 4


def test_uniprotrestclient_fetch_proteins(monkeypatch, capsys, sb_resources, sb_helpers):
    def patch_query_uniprot_search(*args, **kwargs):
        print("patch_query_uniprot_search\nargs: %s\nkwargs: %s" % (args, kwargs))
        client.results_file.write('''# Search: inx15
A8XEF9	A8XEF9_CAEBR	381	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
O61786	O61786_CAEEL	382	6239	Caenorhabditis elegans	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0H5SBJ0	A0A0H5SBJ0_BRUMA	129	6279	Brugia malayi (Filarial nematode worm)	Innexin	Function (1); Sequence similarities (1); Subcellular location (1)
E3MGD6	E3MGD6_CAERE	384	31234	Caenorhabditis remanei (Caenorhabditis vulgaris)	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
//
# Search: inx16
O61787	INX16_CAEEL	372	6239	Caenorhabditis elegans	Innexin-16 (Protein opu-16)	Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V1AZ11	A0A0V1AZ11_TRISP	406	6334	Trichinella spiralis (Trichina worm)	Innexin	Caution (1); Function (1); Sequence similarities (1); Subcellular location (2)
A8XEF8	A8XEF8_CAEBR	374	6238	Caenorhabditis briggsae	Innexin	Function (1); Sequence similarities (1); Subcellular location (2)
A0A0B2VB60	A0A0B2VB60_TOXCA	366	6265	Toxocara canis (Canine roundworm)	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
A0A0V0W5E2	A0A0V0W5E2_9BILA	410	92179	Trichinella sp. T6	Innexin	Caution (2); Function (1); Sequence similarities (1); Subcellular location (1)
//''', "w")
        return

    def patch_query_uniprot_fetch(*args, **kwargs):
        print("patch_query_uniprot_fetch\nargs: %s\nkwargs: %s" % (args, kwargs))
        with open("%s/mock_resources/test_databasebuddy_clients/uniprot_fetch.txt" % sb_resources.res_path, "r") \
                as ifile:
            client.results_file.write(ifile.read(), "w")
        return

    def patch_query_uniprot_fetch_nothing(*args, **kwargs):
        print("patch_query_uniprot_fetch_nothing\nargs: %s\nkwargs: %s" % (args, kwargs))
        client.results_file.write("# Search: A8XEF9,O61786,A0A0H5SBJ0,E3MGD6,O61787,A0A0V1AZ11,A8XEF8,A0A0B2VB60,"
                                  "A0A0V0W5E2\n//\n//", "w")
        return

    dbbuddy = Db.DbBuddy("inx15,inx16")
    client = Db.UniProtRestClient(dbbuddy)
    client.fetch_proteins()

    out, err = capsys.readouterr()
    assert err == out == ""

    # Test a single call to query_uniprot
    monkeypatch.setattr(Db.UniProtRestClient, "query_uniprot", patch_query_uniprot_search)
    client.search_proteins()
    monkeypatch.setattr(Db.UniProtRestClient, "query_uniprot", patch_query_uniprot_fetch)
    client.fetch_proteins()
    out, err = capsys.readouterr()
    assert "Requesting 9 full records from UniProt..." in err

    # Test multicore call to query_uniprot
    monkeypatch.setattr(br, "run_multicore_function", patch_query_uniprot_fetch)
    for accn, rec in client.dbbuddy.records.items():
        rec.record = None
    client.dbbuddy.records["a" * 999] = Db.Record("a" * 999, _database="uniprot")
    client.fetch_proteins()
    out, err = capsys.readouterr()
    assert "Requesting 10 full records from UniProt..." in err
    assert sb_helpers.string2hash(str(client.dbbuddy.records["A8XEF9"].record.seq)) == "04f13629336cf6cdd5859c8913b742a5"

    # Some edge cases
    monkeypatch.setattr(Db.UniProtRestClient, "query_uniprot", patch_query_uniprot_fetch_nothing)
    client.http_errors_file.write("inx15\n%s\n//\n" % URLError("Fake URLError from Mock"))

    client.dbbuddy.records = OrderedDict([("a" * 999, Db.Record("a" * 999, _database="uniprot"))])
    client.fetch_proteins()
    out, err = capsys.readouterr()
    assert "Requesting 1 full records from UniProt..." in err
    assert "No sequences returned\n\n" in err
    assert "The following errors were encountered while querying UniProt with fetch_proteins():" in err
    assert sb_helpers.string2hash(str(client.dbbuddy.records["a" * 999])) == "670bf9c6ae5832b42841798d882a7276"

    with pytest.raises(ValueError) as err:
        client.dbbuddy.records["a" * 1001] = Db.Record("a" * 1001, _database="uniprot")
        client.fetch_proteins()
    assert "The provided accession or search term is too long (>1000)." in str(err)


# NCBI
def test_ncbiclient_init():
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[:3]))
    client = Db.NCBIClient(dbbuddy)
    assert client.Entrez.email == br.config_values()['email']
    assert client.Entrez.tool == "buddysuite"
    assert hash(dbbuddy) == hash(client.dbbuddy)
    assert type(client.http_errors_file) == br.TempFile
    assert type(client.results_file) == br.TempFile
    assert client.max_url == 1000
    assert client.max_attempts == 5


def test_ncbiclient_mc_query(sb_resources, sb_helpers, monkeypatch):
    def patch_entrez_esummary_taxa(*args, **kwargs):
        print("patch_entrez_esummary_taxa\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_esummary_taxa.xml" % sb_resources.res_path
        return open(test_file, "r")

    def patch_entrez_efetch_gis(*args, **kwargs):
        print("patch_entrez_efetch_gis\nargs: %s\nkwargs: %s" % (args, kwargs))
        tmp_file = br.TempFile()
        tmp_file.write("703125407\n703125412\n67586143\n")
        return tmp_file.get_handle("r")

    def patch_entrez_esummary_seq(*args, **kwargs):
        print("patch_entrez_esummary_seq\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_esummary_seq.xml" % sb_resources.res_path
        return open(test_file, "r")

    def patch_entrez_efetch_seq(*args, **kwargs):
        print("patch_entrez_efetch_seq\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_efetch_seq.gb" % sb_resources.res_path
        return open(test_file, "r")

    monkeypatch.setattr(Db, "sleep", lambda _: True)  # No need to wait around for stuff...
    dbbuddy = Db.DbBuddy()
    client = Db.NCBIClient(dbbuddy)

    monkeypatch.setattr(Db.Entrez, "esummary", patch_entrez_esummary_taxa)
    client._mc_query("649,734,1009,2302", ["esummary_taxa"])
    assert sb_helpers.string2hash(client.results_file.read()) == "acfb85bbdf7c2f8ea7e925c5bfcaaf06"
    client.results_file.clear()

    monkeypatch.setattr(Db.Entrez, "efetch", patch_entrez_efetch_gis)
    client._mc_query("XP_010103297.1,XP_010103298.1,XP_010103299.1", ["efetch_gi"])
    assert client.results_file.read() == "703125407\n703125412\n67586143\n### END ###\n"
    client.results_file.clear()

    monkeypatch.setattr(Db.Entrez, "esummary", patch_entrez_esummary_seq)
    client._mc_query("703125407,703125412,67586143", ["esummary_seq"])
    assert sb_helpers.string2hash(client.results_file.read()) == "e6ba80b5fe2f35002ac2227ca7791c17"
    client.results_file.clear()

    monkeypatch.setattr(Db.Entrez, "efetch", patch_entrez_efetch_seq)
    client._mc_query("703125407,703125412,67586143", ["efetch_seq"])
    assert sb_helpers.string2hash(client.results_file.read()) == "0154d7bd9d47ca6abac00f25428b9e7e"

    monkeypatch.undo()
    monkeypatch.setattr(Db, "sleep", lambda _: True)
    with pytest.raises(ValueError) as err:
        client._mc_query("703125407", ["foo"])
    assert "'tool' argument must be in 'esummary_taxa', 'efetch_gi', 'esummary_seq', or 'efetch_seq'" in str(err)

    monkeypatch.setattr(Db.Entrez, "efetch", mock_urlopen_raise_httperror)
    client._mc_query("703125407,703125412,67586143", ["efetch_seq"])
    assert "NCBI request failed: 703125407,703125412,67586143\nHTTP Error 101: Fake HTTPError from Mock\n//" \
           in client.http_errors_file.read()


def test_ncbiclient_search_ncbi(sb_resources, monkeypatch, capsys):
    def patch_entrez_esearch(*args, **kwargs):
        print("patch_entrez_esearch\nargs: %s\nkwargs: %s" % (args, kwargs))
        if "rettype" in kwargs:
            test_file = br.TempFile()
            test_file.write("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE eSearchResult PUBLIC "-//NLM//DTD esearch 20060628//EN" "http://eutils.ncbi.nlm.nih.gov/eutils/dtd/20060628/esearch.dtd">
<eSearchResult>
    <Count>5</Count>
</eSearchResult>
""")
            handle = test_file.get_handle(mode="r")
        else:
            handle = open("%s/mock_resources/test_databasebuddy_clients/Entrez_esearch.xml" % sb_resources.res_path,
                          "r")
        return handle

    monkeypatch.setattr(Db.Entrez, "esearch", patch_entrez_esearch)
    monkeypatch.setattr(Db.NCBIClient, "fetch_summaries", lambda _: True)
    monkeypatch.setattr(Db, "sleep", lambda _: True)
    dbbuddy = Db.DbBuddy("909549231")
    dbbuddy.search_terms = ["casp9"]
    client = Db.NCBIClient(dbbuddy)

    client.search_ncbi("protein")
    for accn in ["909549231", "909549227", "909549224", "909546647", "306819620"]:
        assert accn in dbbuddy.records

    monkeypatch.setattr(Db.Entrez, "esearch", mock_urlopen_raise_keyboardinterrupt)
    client.search_ncbi("protein")
    out, err = capsys.readouterr()
    assert "NCBI query interrupted by user" in err


def test_ncbiclient_fetch_summaries(sb_resources, sb_helpers, monkeypatch):
    # ToDo: add a multicore test
    def patch_entrez_fetch_summaries(*args, **kwargs):
        print("patch_entrez_fetch_summaries\nargs: %s\nkwargs: %s" % (args, kwargs))
        if kwargs["func_args"] == ["esummary_seq"]:
            test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_esummary_seq.xml" % sb_resources.res_path
            with open(test_file, "r") as ifile:
                client.results_file.write(ifile.read().strip())
                client.results_file.write('\n### END ###\n')
        elif kwargs["func_args"] == ["esummary_taxa"]:
            test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_esummary_taxa.xml" % sb_resources.res_path
            with open(test_file, "r") as ifile:
                client.results_file.write(ifile.read().strip())
                client.results_file.write('\n### END ###\n')
        elif kwargs["func_args"] == ["efetch_gi"]:
            client.results_file.write("""703125407
703125412
67586143
### END ###
""")
        return

    # No records to fetch
    dbbuddy = Db.DbBuddy()
    client = Db.NCBIClient(dbbuddy)
    client.fetch_summaries("ncbi_prot")
    assert not client.dbbuddy.records

    monkeypatch.setattr(Db.NCBIClient, "_mc_query", patch_entrez_fetch_summaries)
    dbbuddy = Db.DbBuddy("XP_010103297,XP_010103298.1,67586143,257467473")
    client = Db.NCBIClient(dbbuddy)
    client.fetch_summaries("ncbi_prot")
    for accn, rec in dbbuddy.records.items():
        assert rec.gi in [703125407, 703125412, 67586143, 257467473]
    assert dbbuddy.records["AAY72386.1"].summary["organism"] == "Unclassified"
    assert sb_helpers.string2hash(str(dbbuddy)) == "0cf7c9ccf058cf3b50d2aab7ecb1f953"


def test_ncbiclient_fetch_sequences(sb_resources, sb_helpers, monkeypatch, capsys):
    def patch_entrez_fetch_seq(*args, **kwargs):
        print("patch_entrez_fetch_seq\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_file = "%s/mock_resources/test_databasebuddy_clients/Entrez_efetch_seq.gb" % sb_resources.res_path
        with open(test_file, "r") as ifile:
            client.results_file.write(ifile.read())

    # Empty DbBuddy
    dbbuddy = Db.DbBuddy()
    client = Db.NCBIClient(dbbuddy)
    client.fetch_sequences("ncbi_prot")
    assert sb_helpers.string2hash(str(dbbuddy)) == "016d020dd926f64ac1431f15c5683678"

    # With records
    monkeypatch.setattr(Db.NCBIClient, "_mc_query", patch_entrez_fetch_seq)
    dbbuddy = Db.DbBuddy("XP_010103297.1,XP_010103298.1,XM_010104998.1")
    client = Db.NCBIClient(dbbuddy)
    client.fetch_sequences("ncbi_prot")
    dbbuddy.out_format = "gb"
    assert sb_helpers.string2hash(str(dbbuddy)) == "9bd8017da009696c1b6ebe5d4e3c0a89"
    capsys.readouterr()  # Clean up the buffer
    dbbuddy.print()
    out, err = capsys.readouterr()
    out = re.sub(".*?sec.*?\n", "", out)
    assert sb_helpers.string2hash(out) == "f1614694fd87ffd85ad0b9fa951d4b1d"

    # Error
    monkeypatch.setattr(Db.NCBIClient, "_mc_query", mock_urlopen_raise_keyboardinterrupt)
    client.fetch_sequences("ncbi_prot")
    out, err = capsys.readouterr()
    assert "\n\tNCBI query interrupted by user\n" in err


# ENSEMBL
def test_ensembl_init(monkeypatch, sb_resources):
    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
        if "info/species" in args:
            with open("%s/ensembl_species.json" % test_files, "r") as ifile:
                return json.load(ifile)

    def patch_ensembl_perform_rest_action_empty(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        return {}

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    client = Db.EnsemblRestClient(dbbuddy)
    assert hash(dbbuddy) == hash(client.dbbuddy)
    assert type(client.http_errors_file) == br.TempFile
    assert type(client.results_file) == br.TempFile
    assert client.max_url == 1000
    assert 'vicugnapacos' in client.species['Alpaca']['aliases']

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action_empty)
    client = Db.EnsemblRestClient(dbbuddy)
    assert client.species == {}


def test_ensembl_mc_search(monkeypatch, sb_resources):
    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
        if "info/species" in args:
            with open("%s/ensembl_species.json" % test_files, "r") as ifile:
                return json.load(ifile)
        elif "lookup/symbol/Mouse/Panx1" in args:
            return json.loads('{"id": "ENSMUSG00000031934", "end": 15045478, "seq_region_name": "9", "description": '
                              '"pannexin 1 [Source:MGI Symbol;Acc:MGI:1860055]", "logic_name": "ensembl_havana_gene", '
                              '"species": "Mouse", "strand": -1, "start": 15005161, "db_type": "core", "assembly_name":'
                              ' "GRCm38", "biotype": "protein_coding", "version": 13, "display_name": "Panx1", '
                              '"source": "ensembl_havana", "object_type": "Gene"}')

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    client = Db.EnsemblRestClient(dbbuddy)
    client._mc_search('Mouse', ['Panx1'])
    assert "'description': 'pannexin 1 [Source:MGI Symbol;Acc:MGI:1860055]'" in client.results_file.read()

    monkeypatch.undo()
    monkeypatch.setattr(Db, "Request", mock_urlopen_raise_httperror)
    client._mc_search('Mouse', ['Panx1'])
    assert "HTTP Error 101: Fake HTTPError from Mock" in client.http_errors_file.read()


def test_ensembl_perform_rest_action(monkeypatch, sb_resources, sb_helpers):
    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
        with open("%s/ensembl_species.json" % test_files, "r") as ifile:
            return json.load(ifile)

    def patch_ensembl_urlopen(*args, **kwargs):
        print("patch_ensembl_urlopen\nargs: %s\nkwargs: %s" % (args, kwargs))
        outfile.clear()
        if "lookup/symbol/Mouse/Panx1" in args[0].full_url:
            outfile.write('{"id": "ENSMUSG00000031934", "end": 15045478, "seq_region_name": "9", "description": '
                          '"pannexin 1 [Source:MGI Symbol;Acc:MGI:1860055]", "logic_name": "ensembl_havana_gene", '
                          '"species": "Mouse", "strand": -1, "start": 15005161, "db_type": "core", "assembly_name":'
                          ' "Foo", "biotype": "protein_coding", "version": 13, "display_name": "Panx1", '
                          '"source": "ensembl_havana", "object_type": "Gene"}'.encode())
        elif "lookup/id" in args[0].full_url:
            outfile.write('{"ENSPTRG00000014529":{"source":"ensembl","object_type":"Gene","logic_name":"ensembl",'
                          '"version":5,"species":"pan_troglodytes",'
                          '"description":"pannexin 2 [Source:VGNC Symbol;Acc:VGNC:5291]",'
                          '"display_name":"PANX_tuba!","assembly_name":"CHIMP2.1.4","biotype":"protein_coding",'
                          '"end":49082954,"seq_region_name":"22","db_type":"core","strand":1,'
                          '"id":"ENSPTRG00000014529","start":49073399}}'.encode())
        elif "sequence/id" in args[0].full_url:
            test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
            with open("%s/ensembl_sequence.seqxml" % test_files, "r") as ifile:
                outfile.write(ifile.read().encode())
        elif "error400" in args[0].full_url:
            raise HTTPError(url="http://fake.come", code=400, msg="Bad request", hdrs="Foo", fp="Bar")
        elif "error429" in args[0].full_url:
            raise HTTPError(url="http://fake.come", code=429, msg="Server busy", hdrs={'Retry-After': 0}, fp="Bar")
        return outfile.get_handle("r")

    outfile = br.TempFile(byte_mode=True)
    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    client = Db.EnsemblRestClient(dbbuddy)
    monkeypatch.undo()  # Need to release perform_rest_action
    monkeypatch.setattr(Db, "urlopen", patch_ensembl_urlopen)
    # Search for gene identifiers and return summaries
    data = client.perform_rest_action("lookup/symbol/Mouse/Panx1",
                                      headers={"Content-type": "application/json", "Accept": "application/json"})
    assert data['assembly_name'] == 'Foo'

    # Get summary from accn numbers
    data = client.perform_rest_action("lookup/id", data={"ids": ["ENSPTRG00000014529"]},
                                      headers={"Content-type": "application/json", "Accept": "application/json"})
    assert data["ENSPTRG00000014529"]["display_name"] == "PANX_tuba!"

    # Fetch sequence from accn numbers
    data = client.perform_rest_action("sequence/id", data={"ids": ["ENSPTRG00000014529"]},
                                      headers={"Content-type": "text/x-seqxml+xml"})
    assert sb_helpers.string2hash(next(data).format("embl")) == "f4bb7d1ec812824b51f14d152e156f8f"

    # Unrecognized endpoint header
    with pytest.raises(ValueError) as err:
        client.perform_rest_action("unknown/endpoint", headers={"Content-type": "Foo/Bar"})
    assert "Unknown request headers '{'Content-type': 'Foo/Bar'}'" in str(err)

    # 400 error (with retry)
    client.perform_rest_action("error400")
    client.parse_error_file()
    assert not client.dbbuddy.failures

    # 429 error (with retry)
    client.perform_rest_action("error429")
    client.parse_error_file()
    assert "39eaff4d057aa3d9d098be5cb50d2ce2" in client.dbbuddy.failures

    # URLError
    monkeypatch.setattr(Db, "urlopen", mock_urlopen_raise_urlerror)
    client.perform_rest_action("URLError")
    client.parse_error_file()
    assert 'eb498f0bcba3bfe69e4df6ee5bfbf6fb' in client.dbbuddy.failures

    # URLError 8 (no internet)
    monkeypatch.setattr(Db, "urlopen", mock_urlopen_raise_urlerror_8)
    client.perform_rest_action("URLError")
    client.parse_error_file()
    assert '57ad6fc317cf0d12ccb78d64d43682dc' in client.dbbuddy.failures


def test_search_ensembl(monkeypatch, capsys, sb_resources, sb_helpers):
    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        with open("%s/ensembl_species.json" % test_files, "r") as ifile:
            return json.load(ifile)

    def patch_search_ensembl_empty(*args, **kwargs):
        print("patch_search_ensembl_empty\nargs: %s\nkwargs: %s" % (args, kwargs))
        return

    def patch_search_ensembl_results(*args, **kwargs):
        print("patch_search_ensembl_empty\nargs: %s\nkwargs: %s" % (args, kwargs))
        with open("%s/ensembl_search_results.txt" % test_files, "r") as ifile:
            client.results_file.write(ifile.read())
        return

    test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    monkeypatch.setattr(br, "run_multicore_function", patch_search_ensembl_empty)

    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    client = Db.EnsemblRestClient(dbbuddy)
    client.dbbuddy.search_terms = ["Panx3"]
    client.dbbuddy.records["ENSLAFG00000006034"] = Db.Record("ENSLAFG00000006034")
    client.search_ensembl()
    out, err = capsys.readouterr()
    assert err == "Searching Ensembl for Panx3...\nEnsembl returned no results\n"
    assert not client.dbbuddy.records["ENSLAFG00000006034"].record

    monkeypatch.setattr(br, "run_multicore_function", patch_search_ensembl_results)
    client.search_ensembl()
    assert sb_helpers.string2hash(str(client.dbbuddy)) == "95dc1ecce077bef84cdf2d85ce154eef"
    assert len(client.dbbuddy.records) == 44
    assert client.dbbuddy.records["ENSLAFG00000006034"].database == "ensembl"


def test_ensembl_fetch_summaries(monkeypatch, capsys, sb_resources, sb_helpers):
    def patch_species_fetch(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
        with open("%s/ensembl_species.json" % test_files, "r") as ifile:
            return json.load(ifile)

    def patch_ensembl_perform_rest_action_no_return(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        return {}

    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        return {'ENSCJAG00000008732': {'start': 49787361, 'logic_name': 'ensembl', 'display_name': 'Foo',
                                       'seq_region_name': '7', 'version': 2, 'biotype': 'protein_coding',
                                       'object_type': 'Gene', 'source': 'ensembl', 'end': 49814140,
                                       'assembly_name': 'C_jacchus3.2.1', 'db_type': 'core',
                                       'description': 'caspase 9 [Source:HGNC Symbol;Acc:HGNC:1511]',
                                       'strand': -1, 'id': 'ENSCJAG00000008732'},
                'ENSAMEG00000011912': {}}

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_species_fetch)
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    client = Db.EnsemblRestClient(dbbuddy)

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action_no_return)
    client.fetch_summaries()
    capsys.readouterr()
    client.dbbuddy.print()
    out, err = capsys.readouterr()
    assert sb_helpers.string2hash(out + err) == "8e1a0cda099ec052a26cd6e02a863443"

    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    client.fetch_summaries()
    capsys.readouterr()
    client.dbbuddy.print()
    out, err = capsys.readouterr()
    assert sb_helpers.string2hash(out + err) == "282c625cbb95d6e7fa1a46dcd86299d0"
    assert client.dbbuddy.records['ENSCJAG00000008732'].summary['name'] == "Foo"


def test_ensembl_fetch_nucleotide(monkeypatch, capsys, sb_resources, sb_helpers):
    def patch_ensembl_perform_rest_action(*args, **kwargs):
        print("patch_ensembl_perform_rest_action\nargs: %s\nkwargs: %s" % (args, kwargs))
        if "info/species" in args:
            with open("%s/ensembl_species.json" % test_files, "r") as ifile:
                return json.load(ifile)
        elif "sequence/id" in args:
            with open("%s/ensembl_sequence.seqxml" % test_files, "r") as ifile:
                tmp_file = br.TempFile(byte_mode=True)
                tmp_file.write(ifile.read().encode())
                return Db.SeqIO.parse(tmp_file.get_handle("r"), "seqxml")

    test_files = "%s/mock_resources/test_databasebuddy_clients/" % sb_resources.res_path
    monkeypatch.setattr(Db.EnsemblRestClient, "perform_rest_action", patch_ensembl_perform_rest_action)
    dbbuddy = Db.DbBuddy(", ".join(ACCNS[7:]))
    dbbuddy.records['ENSAMEG00000011912'] = Db.Record('ENSAMEG00000011912')
    summary = OrderedDict([('organism', 'macropus_eugenii'), ('comments', 'Blahh blahh blahh'), ('name', 'Foo1')])
    dbbuddy.records['ENSCJAG00000008732'].summary = summary

    client = Db.EnsemblRestClient(dbbuddy)
    client.fetch_nucleotide()

    capsys.readouterr()
    client.dbbuddy.print()
    out, err = capsys.readouterr()
    assert sb_helpers.string2hash(out + err) == "4b38cb4ce35d4503603a44e49c7e34b4"
