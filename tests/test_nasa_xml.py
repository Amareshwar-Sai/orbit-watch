"""NASA-like embedded HTML must not disable protection from actual XML DTDs."""
import unittest
from orbitwatch.ingest import parse_feed


def feed(description):
    return ('<rss version="2.0"><channel><item><title>Satellite news</title>'
            '<link>https://example.org/report</link><description>' + description +
            '</description></item></channel></rss>').encode('utf-8')


class NASAFeedTests(unittest.TestCase):
    def test_html_doctype_inside_cdata(self):
        value = '<![CDATA[<p><!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd"><br /><html><body>Space report</body></html></p>]]>'
        rows = parse_feed(feed(value))
        self.assertEqual(len(rows), 1)
        self.assertIn('Space report', rows[0]['summary'])

    def test_entity_text_inside_cdata_is_inert(self):
        self.assertEqual(len(parse_feed(feed('<![CDATA[Example: <!ENTITY sample "text">]]>'))), 1)

    def test_declaration_in_comment_is_inert(self):
        self.assertEqual(len(parse_feed(feed('<!-- <!DOCTYPE html> -->Report'))), 1)

    def test_external_dtd_rejected(self):
        raw = b'<!DOCTYPE rss SYSTEM "https://example.org/evil.dtd"><rss/>'
        with self.assertRaisesRegex(ValueError, 'declarations are forbidden'):
            parse_feed(raw)

    def test_internal_entity_rejected(self):
        raw = b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss>&x;</rss>'
        with self.assertRaisesRegex(ValueError, 'declarations are forbidden'):
            parse_feed(raw)

    def test_parameter_entity_rejected(self):
        raw = b'<!DOCTYPE rss [<!ENTITY % x SYSTEM "file:///etc/passwd">%x;]><rss/>'
        with self.assertRaisesRegex(ValueError, 'declarations are forbidden'):
            parse_feed(raw)

    def test_cdata_does_not_hide_later_invalid_declaration(self):
        with self.assertRaises(ValueError):
            parse_feed(feed('<![CDATA[safe]]><!DOCTYPE html>'))

    def test_malformed_xml_is_reportable_error(self):
        with self.assertRaisesRegex(ValueError, 'Malformed XML feed'):
            parse_feed(b'<rss><channel></rss>')


if __name__ == '__main__':
    unittest.main()
