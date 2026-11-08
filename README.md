# teste-de-ci-cd

[![CI](https://github.com/RikThaylon/teste-de-ci-cd/actions/workflows/ci.yml/badge.svg)](https://github.com/RikThaylon/teste-de-ci-cd/actions/workflows/ci.yml)

Repositório para praticar CI/CD usando um projeto real: o pacote de **13 skills
do Claude para Instagram** criado por Jake Schincariol
([Jakeschincariol/instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill),
licença MIT).

O código das skills veio do repositório original sem alterações. O que foi
adicionado aqui é a parte de CI: testes automáticos e um workflow do GitHub
Actions que roda esses testes a cada push.

A documentação completa do autor, em inglês, está em [README.en.md](README.en.md).

## O que tem aqui

```
.claude-plugin/        manifesto para instalar como plugin do Claude Code
skills/ig-*/           as 13 skills (cada uma tem um SKILL.md)
  ig-reel/             hookscore.py e beats.py   (nota do gancho e tempo do roteiro)
  ig-caption/          caption.py                (revisão da legenda)
  ig-human/            humanize.py e detect.py   (limpa e avalia texto gerado por IA)
  ig-viral/            swipe.py                  (ranking de Reels por desempenho relativo)
templates/voice.md     modelo do seu "tom de voz", lido por todas as skills
tests/test_skills.py   testes automáticos (adicionado neste repo)
.github/workflows/     o pipeline de CI (adicionado neste repo)
```

Os 6 scripts Python usam só a biblioteca padrão: não precisam de `pip install`,
não acessam a internet e só gravam arquivo quando você passa `--out`.

## Como o CI funciona

O arquivo [`.github/workflows/ci.yml`](.github/workflows/ci.yml) diz ao GitHub:

1. **Quando rodar:** em todo push, em pull requests para a `main` e
   manualmente pela aba *Actions*.
2. **Onde rodar:** numa máquina Ubuntu nova, em duas versões do Python (3.10 e
   3.12) ao mesmo tempo. Isso se chama *matriz*.
3. **O que rodar:** `python -m unittest discover -s tests -v`.

Os testes em [`tests/test_skills.py`](tests/test_skills.py) verificam:

- se todos os arquivos `.json` são válidos;
- se existem 13 skills e cada `SKILL.md` tem `name` e `description`;
- se cada script compila e responde ao `--help`;
- o comportamento de cada script com entradas conhecidas. Por exemplo: um
  gancho que começa com "Hey guys" precisa tirar nota menor que um gancho com
  um número concreto, e uma legenda com 6 hashtags precisa ser reprovada.

Para ver o resultado, abra a aba **Actions** do repositório no GitHub.

## Rodar os testes no seu computador

Na raiz do repositório:

```bash
python -m unittest discover -s tests -v
```

## Usar as skills no Claude Code

Copie as pastas para a sua pasta de skills:

```bash
cp -r skills/ig-* ~/.claude/skills/
```

Ou instale como plugin a partir deste repositório:

```
/plugin marketplace add RikThaylon/teste-de-ci-cd
/plugin install instagram-agent
```

Depois preencha `templates/voice.md` (copie para `~/.claude/instagram/voice.md`).
Todas as skills leem esse arquivo.

## Licença

MIT. O aviso de copyright do autor original está em [LICENSE](LICENSE).
