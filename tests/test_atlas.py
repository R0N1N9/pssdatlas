import math
import unittest

from pssd_atlas import classify, config, faers, pubmed

CFG = config.load()


def rec(title="", abstract="", pub_types=(), mesh=()):
    return {"title": title, "abstract": abstract, "pub_types": list(pub_types), "mesh": list(mesh)}


class StudyType(unittest.TestCase):
    def test_publication_types_win(self):
        self.assertEqual(classify.study_type(rec("x", pub_types=["Randomized Controlled Trial"])), "rct")
        self.assertEqual(classify.study_type(rec("x", pub_types=["Case Reports", "Review"])), "case_report")
        self.assertEqual(classify.study_type(rec("x", pub_types=["Journal Article", "Review"])), "review")
        self.assertEqual(classify.study_type(rec("x", pub_types=["Systematic Review"])), "systematic_review")

    def test_animal_by_mesh_or_title(self):
        self.assertEqual(classify.study_type(rec("Paroxetine effects", mesh=["Animals", "Rats"])), "animal")
        self.assertEqual(classify.study_type(rec("Paroxetine effects", mesh=["Animals", "Humans"],
                                                 abstract="A survey of 100 patients.")), "observational")
        self.assertEqual(classify.study_type(rec("Persistent effects of paroxetine in male rats")), "animal")

    def test_text_fallbacks(self):
        self.assertEqual(classify.study_type(rec("Post-SSRI sexual dysfunction: a case report")), "case_report")
        self.assertEqual(classify.study_type(rec("PSSD", "An online survey of 300 respondents.")), "observational")
        self.assertEqual(classify.study_type(rec("Something else entirely", "Text.")), "other")


class Tagging(unittest.TestCase):
    def test_hypotheses_interventions_drugs(self):
        r = classify.classify_paper(rec(
            "Allopregnanolone and 5-HT1A receptors after paroxetine",
            "Bupropion and sildenafil were tried. Olanzapine was also taken."), CFG)
        self.assertIn("neurosteroid", r["hypotheses"])
        self.assertIn("serotonin", r["hypotheses"])
        self.assertEqual(set(r["interventions"]), {"bupropion", "pde5"})
        self.assertEqual(set(r["drugs"]), {"paroxetine", "bupropion", "olanzapine"})

    def test_trial_relevance(self):
        t = {"title": "Study of Guselkumab in PSSD", "conditions": ["Psoriasis"], "summary": ""}
        self.assertIsNone(classify.trial_scope(t, CFG))
        t = {"title": "Treatment of Post-SSRI Sexual Dysfunction", "conditions": [], "summary": ""}
        self.assertEqual(classify.trial_scope(t, CFG), "core")
        t = {"title": "Bupropion for SSRI-induced sexual dysfunction", "conditions": [], "summary": ""}
        self.assertEqual(classify.trial_scope(t, CFG), "adjacent")


class Disproportionality(unittest.TestCase):
    def test_known_values(self):
        # a=20, b=80, c=100, d=9800 -> ROR = (20/80)/(100/9800) = 24.5; PRR = 0.2/(100/9900) = 19.8
        r = faers.disproportionality(a=20, drug_total=100, reaction_total=120, n=10000)
        self.assertEqual((r["a"], r["b"], r["c"], r["d"]), (20, 80, 100, 9800))
        self.assertAlmostEqual(r["ror"], 24.5)
        self.assertAlmostEqual(r["prr"], 19.8)
        se = math.sqrt(1 / 20 + 1 / 80 + 1 / 100 + 1 / 9800)
        self.assertAlmostEqual(r["ror_lo"], 24.5 * math.exp(-1.96 * se))
        self.assertTrue(r["signal"])

    def test_no_signal_and_undefined(self):
        r = faers.disproportionality(a=10, drug_total=1000, reaction_total=100, n=10000)
        self.assertAlmostEqual(r["ror"], 1.0, places=1)
        self.assertFalse(r["signal"])
        r = faers.disproportionality(a=0, drug_total=1000, reaction_total=100, n=10000)
        self.assertIsNone(r["ror"])
        self.assertFalse(r["signal"])


class PubmedParse(unittest.TestCase):
    def test_parse(self):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
        <Journal><JournalIssue><PubDate><MedlineDate>2019 Jan-Feb</MedlineDate></PubDate></JournalIssue>
        <ISOAbbreviation>J Test</ISOAbbreviation></Journal>
        <ArticleTitle>Post-SSRI <i>sexual</i> dysfunction.</ArticleTitle>
        <Abstract><AbstractText Label="AIM">One.</AbstractText><AbstractText>Two.</AbstractText></Abstract>
        <AuthorList><Author><LastName>Doe</LastName><Initials>J</Initials></Author></AuthorList>
        <PublicationTypeList><PublicationType>Case Reports</PublicationType></PublicationTypeList></Article>
        <MeshHeadingList><MeshHeading><DescriptorName>Humans</DescriptorName></MeshHeading></MeshHeadingList>
        </MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/x</ArticleId></ArticleIdList>
        </PubmedData></PubmedArticle></PubmedArticleSet>"""
        (p,) = pubmed.parse(xml)
        self.assertEqual(p["id"], "PMID:123")
        self.assertEqual(p["title"], "Post-SSRI sexual dysfunction.")
        self.assertEqual(p["abstract"], "AIM: One. Two.")
        self.assertEqual((p["year"], p["doi"], p["authors"], p["mesh"]), (2019, "10.1/x", ["Doe J"], ["Humans"]))


if __name__ == "__main__":
    unittest.main()
