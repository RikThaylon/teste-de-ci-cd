"""
Testes automáticos das skills de Instagram.

Rodam no GitHub Actions a cada push (veja .github/workflows/ci.yml), mas você
também pode rodar no seu computador, a partir da raiz do repositório:

    python -m unittest discover -s tests -v

Só usam a biblioteca padrão do Python (unittest, subprocess, json), então não
precisa instalar nada.

A ideia de cada teste é simples: rodar um script do jeito que uma pessoa
rodaria no terminal, com uma entrada conhecida, e conferir se a saída é a
esperada. Se alguém mudar o código e quebrar um comportamento, o CI fica
vermelho e avisa antes de o problema chegar na branch principal.
"""

import json
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILLS = RAIZ / "skills"

SCRIPTS = [
    "ig-caption/caption.py",
    "ig-human/detect.py",
    "ig-human/humanize.py",
    "ig-reel/beats.py",
    "ig-reel/hookscore.py",
    "ig-viral/swipe.py",
]


def rodar(script, *args, entrada=None):
    """Executa um script da pasta skills/ e devolve o resultado (código de saída, stdout, stderr)."""
    return subprocess.run(
        [sys.executable, str(SKILLS / script), *args],
        input=entrada,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def rodar_json(script, *args, entrada=None, codigos_aceitos=(0,)):
    """Executa um script com --json e já converte a saída para dicionário/lista.

    codigos_aceitos: o caption.py sai com 1 sempre que a legenda não está
    perfeita, mesmo com --json, então nesses testes aceitamos 0 ou 1.
    """
    r = rodar(script, *args, "--json", entrada=entrada)
    if r.returncode not in codigos_aceitos:
        raise AssertionError(f"{script} saiu com código {r.returncode}:\n{r.stderr}")
    return json.loads(r.stdout)


class TestEstrutura(unittest.TestCase):
    """Confere se os arquivos do repositório estão bem formados."""

    def test_todos_os_json_sao_validos(self):
        arquivos = [p for p in RAIZ.rglob("*.json") if ".git" not in p.parts]
        self.assertGreater(len(arquivos), 0)
        for caminho in arquivos:
            with self.subTest(arquivo=str(caminho.relative_to(RAIZ))):
                json.loads(caminho.read_text(encoding="utf-8"))

    def test_existem_treze_skills(self):
        pastas = sorted(p.name for p in SKILLS.iterdir() if (p / "SKILL.md").exists())
        self.assertEqual(len(pastas), 13, pastas)

    def test_cada_skill_tem_nome_e_descricao(self):
        # Todo SKILL.md começa com um cabeçalho entre "---" com name e description.
        # O name precisa ser igual ao nome da pasta, senão o Claude não acha a skill.
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            pasta = skill_md.parent.name
            with self.subTest(skill=pasta):
                texto = skill_md.read_text(encoding="utf-8")
                self.assertTrue(texto.startswith("---\n"), "falta o cabeçalho ---")
                cabecalho = texto.split("---", 2)[1]
                linhas = cabecalho.splitlines()
                self.assertIn(f"name: {pasta}", linhas)
                self.assertTrue(any(l.startswith("description:") for l in linhas))

    def test_scripts_compilam(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                py_compile.compile(str(SKILLS / script), doraise=True)

    def test_scripts_mostram_ajuda(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                r = rodar(script, "--help")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("usage:", r.stdout)


class TestHookscore(unittest.TestCase):
    """ig-reel/hookscore.py: dá nota de 0 a 100 para o gancho (primeira frase) de um Reel."""

    BOM = "I lost $18,000 because of one missing contract."
    RUIM = "Hey guys, today I wanted to talk about content strategy"

    def test_gancho_bom_ganha_de_gancho_ruim(self):
        bom, ruim = rodar_json("ig-reel/hookscore.py", "-", entrada=f"{self.BOM}\n{self.RUIM}\n")
        self.assertGreater(bom["score"], ruim["score"])
        self.assertEqual(bom["verdict"], "STRONG")
        self.assertEqual(ruim["verdict"], "WEAK")

    def test_saudacao_e_dealbreaker(self):
        ruim = rodar_json("ig-reel/hookscore.py", "--hook", self.RUIM)
        self.assertTrue(any("Greeting" in f for f in ruim["flags"]), ruim["flags"])

    def test_codigo_de_saida(self):
        # Sai com 0 quando o gancho passa de 70 pontos e com 1 quando não passa.
        self.assertEqual(rodar("ig-reel/hookscore.py", "--hook", self.BOM).returncode, 0)
        self.assertEqual(rodar("ig-reel/hookscore.py", "--hook", self.RUIM).returncode, 1)

    def test_entrada_vazia(self):
        self.assertEqual(rodar("ig-reel/hookscore.py", "-", entrada="").returncode, 2)


class TestBeats(unittest.TestCase):
    """ig-reel/beats.py: transforma o roteiro em uma linha do tempo, uma fala por linha."""

    ROTEIRO = (
        "I lost $18,000 because of one missing contract.\n"
        "Here is the exact clause I now put in every single contract.\n"
        "Section 4. Payment on delivery, not on approval.\n"
        "That one word change is worth $18,000 to me.\n"
    )

    def test_linha_do_tempo(self):
        a = rodar_json("ig-reel/beats.py", "-", "--target", "30", entrada=self.ROTEIRO)
        self.assertEqual(len(a["beats"]), 4)
        self.assertEqual(a["total_words"], 37)          # 8 + 12 + 8 + 9 palavras
        # 165 palavras por minuto = 2,75 palavras por segundo
        self.assertAlmostEqual(a["total_seconds"], 37 / 2.75, places=1)
        self.assertEqual(a["beats"][0]["label"], "HOOK")
        self.assertEqual(a["beats"][-1]["label"], "CTA")

    def test_detecta_loop(self):
        # A última fala repete "$18,000" da primeira, o que incentiva reassistir.
        a = rodar_json("ig-reel/beats.py", "-", entrada=self.ROTEIRO)
        self.assertTrue(any(n.startswith("Loops:") for n in a["notes"]), a["notes"])

    def test_roteiro_vazio(self):
        self.assertEqual(rodar("ig-reel/beats.py", "-", entrada="\n\n").returncode, 2)


class TestCaption(unittest.TestCase):
    """ig-caption/caption.py: revisa a legenda do post."""

    def analisar(self, legenda):
        return rodar_json("ig-caption/caption.py", "-", entrada=legenda, codigos_aceitos=(0, 1))

    def status(self, analise, nome):
        return next(c["status"] for c in analise["checks"] if c["check"] == nome)

    def test_mais_de_cinco_hashtags_falha(self):
        # Desde dezembro de 2025 o Instagram aceita no máximo 5 hashtags por post.
        legenda = "I lost $18,000 on one contract.\n\n#a1 #b2 #c3 #d4 #e5 #f6\n"
        a = self.analisar(legenda)
        self.assertEqual(len(a["hashtags"]), 6)
        self.assertEqual(self.status(a, "HASHTAGS"), "FAIL")
        self.assertEqual(a["verdict"], "FIX")
        self.assertEqual(rodar("ig-caption/caption.py", "-", entrada=legenda).returncode, 1)

    def test_ate_cinco_hashtags_passa(self):
        legenda = "I lost $18,000 on one contract.\n\n#freelance #contracts #agencyowner\n"
        a = self.analisar(legenda)
        self.assertEqual(self.status(a, "HASHTAGS"), "PASS")

    def test_corte_do_feed_em_125_caracteres(self):
        legenda = "x" * 300
        a = self.analisar(legenda)
        self.assertTrue(a["truncated"])
        self.assertEqual(len(a["visible"]), 125)


class TestHumanize(unittest.TestCase):
    """ig-human/humanize.py: limpa marcas típicas de texto gerado por IA."""

    def test_remove_travessao_e_caractere_invisivel(self):
        texto = "Pricing is hard—here is why.​ It took me 3 years to learn.\n"
        r = rodar_json("ig-human/humanize.py", "-", entrada=texto)
        self.assertNotIn("—", r["text"])            # travessão (em dash)
        self.assertNotIn("​", r["text"])            # espaço de largura zero
        self.assertGreaterEqual(len(r["report"]["invisible"]), 1)
        self.assertGreaterEqual(len(r["report"]["typographic"]), 1)

    def test_nao_mexe_em_links(self):
        texto = "Full guide here: https://example.com/pricing-guide\n"
        r = rodar_json("ig-human/humanize.py", "-", entrada=texto)
        self.assertIn("https://example.com/pricing-guide", r["text"])

    def test_grava_arquivo_com_out(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "limpo.txt"
            r = rodar("ig-human/humanize.py", "-", "--out", str(saida), entrada="Hi—there.\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("—", saida.read_text(encoding="utf-8"))


class TestDetect(unittest.TestCase):
    """ig-human/detect.py: dá uma nota de 'quão humano' o texto parece (5 verificações)."""

    def test_compara_antes_e_depois(self):
        with tempfile.TemporaryDirectory() as pasta:
            sujo = Path(pasta) / "antes.txt"
            limpo = Path(pasta) / "depois.txt"
            sujo.write_text("I tried it—twice.​ Then it worked—finally.\n", encoding="utf-8")
            limpo.write_text("I tried it twice. Then it worked, finally.\n", encoding="utf-8")
            antes, depois = rodar_json("ig-human/detect.py", str(sujo), str(limpo))

        for resultado in (antes, depois):
            self.assertEqual(len(resultado["checks"]), 5)
            self.assertGreaterEqual(resultado["human_score"], 0)
            self.assertLessEqual(resultado["human_score"], 100)
            self.assertIn(resultado["verdict"], {"PASS", "REVIEW", "FLAGGED"})

        # Travessões e caracteres invisíveis derrubam a nota de FINGERPRINT.
        self.assertEqual(depois["checks"]["FINGERPRINT"]["score"], 100.0)
        self.assertLess(antes["checks"]["FINGERPRINT"]["score"], 100.0)


class TestSwipe(unittest.TestCase):
    """ig-viral/swipe.py: ordena Reels pelo quanto superaram o tamanho da própria conta."""

    TSV = (
        "account\tfollowers\tviews\thook\n"
        "@a\t4000\t400000\tnobody tells you that your first 30 reels are supposed to flop\n"
        "@b\t2000000\t400000\tin this video I am going to show you my morning routine\n"
        "@c\t3000\t180000\tsteal this four line follow up it took me two years\n"
    )

    def test_ordena_pelo_multiplo_e_nao_pelas_views(self):
        # @a e @b têm as mesmas 400 mil views, mas @a tem 4 mil seguidores (100x)
        # e @b tem 2 milhões (0,2x). O que importa é o múltiplo.
        a = rodar_json("ig-viral/swipe.py", "-", entrada=self.TSV)
        self.assertEqual(a["n"], 3)
        self.assertEqual(a["baseline"], "follower count")
        self.assertEqual([r["account"] for r in a["reels"]], ["@a", "@c", "@b"])
        self.assertEqual([r["outlier"] for r in a["reels"]], [100.0, 60.0, 0.2])

    def test_grava_markdown(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "swipe.md"
            r = rodar("ig-viral/swipe.py", "-", "--out", str(saida), entrada=self.TSV)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(saida.read_text(encoding="utf-8").startswith("# Swipe file"))

    def test_sem_linhas_validas(self):
        self.assertEqual(rodar("ig-viral/swipe.py", "-", entrada="").returncode, 2)


if __name__ == "__main__":
    unittest.main()
