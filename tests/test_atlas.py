import math
import unittest

from pssd_atlas import classify, community, config, faers, forumpage, pubmed, reddit

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


class Partitions(unittest.TestCase):
    def parts(self, title, abstract=""):
        return classify.classify_paper(rec(title, abstract), CFG)["partitions"]

    def test_papers(self):
        self.assertEqual(self.parts("Post-SSRI sexual dysfunction after sertraline"), ["all", "ssri_snri"])
        self.assertEqual(self.parts("Persistent sexual dysfunction after olanzapine"), ["all", "ap_mirt"])
        self.assertEqual(self.parts("Sexual effects of Remeron and venlafaxine"), ["all", "ssri_snri", "ap_mirt"])
        self.assertEqual(self.parts("Post-finasteride syndrome"), ["all"])
        self.assertEqual(self.parts("Antipsychotic-induced sexual dysfunction"), ["all", "ap_mirt"])

    def test_posts_do_not_treat_pssd_as_ssri(self):
        post = {"id": "reddit:1", "source": "reddit", "url": "u", "title": "PSSD from Zyprexa", "text": "Only ever took that."}
        self.assertEqual(community.extract(post, CFG)["partitions"], ["all", "ap_mirt"])


class PatientPosts(unittest.TestCase):
    def test_extract(self):
        post = {"id": "reddit:1", "source": "reddit", "community": "r/PSSD", "url": "u", "date": "2025-01-02",
                "title": "Mirtazipine gave me genital numbness and zero libido",
                "text": "Wellbutrin didn't help at all. Cialis helped a bit with erections. "
                        "Keto made everything worse. I also take magnesium."}
        r = community.extract(post, CFG)
        self.assertEqual(r["drugs"], ["mirtazapine", "bupropion"])
        self.assertEqual(set(r["symptoms"]), {"genital_numbness", "libido", "erectile"})
        got = {t["id"]: t["outcome"] for t in r["treatments"]}
        self.assertEqual(got, {"bupropion": "none", "pde5": "better", "keto_fasting": "worse", "supplements": "mentioned"})
        self.assertFalse(r["recovery"])
        self.assertNotIn("text", r)
        self.assertNotIn("title", r)

    def test_reddit_parse_drops_author(self):
        p = reddit._post({"id": "abc", "subreddit": "PSSD", "permalink": "/r/PSSD/comments/abc/x/", "created_utc": 1700000000,
                          "title": "T", "selftext": "S", "num_comments": 3, "author": "someone"})
        self.assertEqual((p["id"], p["community"], p["date"], p["replies"]), ("reddit:abc", "r/PSSD", "2023-11-14", 3))
        self.assertNotIn("someone", str(p))


class RedditCollect(unittest.TestCase):
    def test_token_paging_and_dedup(self):
        import json, os
        calls = []

        class Fake:
            def get(self, url, params=None, post=False, headers=None, **kw):
                calls.append((url, dict(params or {}), headers))
                if url == reddit.TOKEN_URL:
                    return json.dumps({"access_token": "tok"})
                child = lambda i: {"kind": "t3", "data": {"id": i, "subreddit": "PSSD", "permalink": f"/r/PSSD/{i}/",
                                                           "created_utc": 1700000000, "title": i, "selftext": ""}}
                if "search" in url:
                    return json.dumps({"data": {"children": [child("b")], "after": None}})
                if params.get("after") == "t3_a":
                    return json.dumps({"data": {"children": [child("b")], "after": None}})
                return json.dumps({"data": {"children": [child("a")], "after": "t3_a"}})

        os.environ.update(REDDIT_CLIENT_ID="id", REDDIT_CLIENT_SECRET="secret")
        try:
            posts = reddit.collect(Fake(), {"subreddits": ["PSSD"], "search": [{"subreddit": "PSSD", "q": "x"}]})
        finally:
            del os.environ["REDDIT_CLIENT_ID"], os.environ["REDDIT_CLIENT_SECRET"]
        self.assertEqual(sorted(p["id"] for p in posts), ["reddit:a", "reddit:b"])
        self.assertTrue(calls[0][2]["Authorization"].startswith("Basic "))
        self.assertEqual(calls[1][2]["Authorization"], "Bearer tok")
        self.assertEqual(len(calls), 4)  # token, two listing pages, one search

    def test_missing_credentials(self):
        with self.assertRaises(reddit.MissingCredentials):
            reddit.token(None)


class ForumPages(unittest.TestCase):
    def test_phpbb(self):
        page = """<html><head><title>Zyprexa PSSD - Forum</title><link rel="canonical" href="https://f.example/t/1"></head><body>
        <div class="post"><div class="postbody"><p class="author">by <a>someuser</a> <time datetime="2024-03-05T10:00:00+00:00">x</time></p>
        <div class="content">I took olanzapine for three months and my libido never came back after stopping.<br>Still numb.</div>
        <div class="signature">my sig text here that is long enough to count as a post if wrong</div></div></div>
        <div class="post"><div class="postbody"><p class="author"><time datetime="2024-03-06T10:00:00+00:00">y</time></p>
        <div class="content"><blockquote><div>someuser wrote: I took olanzapine</div></blockquote>Same here with Remeron, bupropion did not help me at all sadly.</div></div></div>
        </body></html>"""
        p = forumpage.parse(page)
        self.assertEqual((p["url"], p["title"], len(p["posts"])), ("https://f.example/t/1", "Zyprexa PSSD - Forum", 2))
        self.assertEqual(p["posts"][0]["date"], "2024-03-05")
        self.assertIn("Still numb", p["posts"][0]["text"])
        self.assertEqual(p["posts"][1]["text"], "Same here with Remeron, bupropion did not help me at all sadly.")
        self.assertNotIn("someuser", " ".join(x["text"] for x in p["posts"]))

    def test_invision_and_fallback(self):
        page = """<!-- saved from url=(0026)https://s.example/topic/9 --><html><body><article><time datetime='2023-01-02T00:00:00Z'>d</time>
        <div data-role='commentContent' class='ipsType_richText'><p>Quetiapine for sleep, then genital numbness that has lasted two years now.</p></div></article></body></html>"""
        p = forumpage.parse(page)
        self.assertEqual((p["url"], len(p["posts"]), p["posts"][0]["date"]), ("https://s.example/topic/9", 1, "2023-01-02"))
        q = forumpage.parse("<html><body><p>Just some saved notes about mirtazapine and what happened afterwards.</p></body></html>")
        self.assertFalse(q["split"])
        self.assertIn("mirtazapine", q["posts"][0]["text"])


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
        self.assertEqual(p["date"], "2019-01")

    def test_dates(self):
        import xml.etree.ElementTree as ET
        d = lambda x: pubmed._date(ET.fromstring(x))
        self.assertEqual(d("<D><Year>2021</Year><Month>Mar</Month><Day>7</Day></D>"), "2021-03-07")
        self.assertEqual(d("<D><Year>2021</Year><Month>11</Month></D>"), "2021-11")
        self.assertEqual(d("<D><Year>2021</Year></D>"), "2021")
        self.assertEqual(d("<D><MedlineDate>2004 Winter</MedlineDate></D>"), "2004")
        self.assertEqual(d("<D></D>"), "")


if __name__ == "__main__":
    unittest.main()
