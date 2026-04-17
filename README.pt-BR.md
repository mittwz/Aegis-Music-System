# Aegis Music System

**Sistema adaptativo de música para Dota 2 e Spotify.**

Este arquivo existe como alternativa em PT-BR. O idioma padrão do projeto e da documentação principal é o inglês.

## Resumo rápido

- escuta o GSI do Dota 2
- detecta estados do jogo
- troca playlist e ajusta volume no Spotify
- possui modo cinema
- possui ganho global de volume

## Uso básico

1. Instale as dependências.
2. Preencha o `.env`.
3. Copie o arquivo em `dota_gsi/` para a pasta `gamestate_integration` do Dota.
4. Rode `python main.py`.

## Configuração importante

O controle principal de volume agora é:

```jsonc
"master_gain_percent": 100
```

Exemplos:

- `70` = mais baixo
- `100` = neutro
- `120` = mais alto
- `140` = bem agressivo

Perfis disponíveis:

- `default`
- `custom_user_electronic`
- `copyrighted_mainstream`

Veja o `README.md` para a documentação principal completa.
