from __future__ import annotations

from clasificador.analysis.rules_config import CampanaRulesConfig, compile_rules


def test_default_config_matches_hardcoded_original_values():
    config = CampanaRulesConfig()
    assert config.boton_cupo == "quiero usar mi cupo"
    assert config.rx_interes_confirmado == "hemos registrado tu inter"
    assert "hola" in config.cortesias


def test_from_json_none_usa_defaults():
    assert CampanaRulesConfig.from_json(None) == CampanaRulesConfig()


def test_from_json_parcial_completa_con_defaults():
    config = CampanaRulesConfig.from_json({"boton_cupo": "quiero mi promo"})
    assert config.boton_cupo == "quiero mi promo"
    # El resto sigue siendo el default, no se pierde por dar solo una clave.
    assert config.rx_interes_confirmado == CampanaRulesConfig().rx_interes_confirmado
    assert config.cortesias == CampanaRulesConfig().cortesias


def test_to_json_from_json_roundtrip():
    original = CampanaRulesConfig(boton_cupo="quiero mi promo", cortesias=("hola", "listo"))
    restored = CampanaRulesConfig.from_json(original.to_json())
    assert restored == original


def test_validar_detecta_regex_invalido():
    config = CampanaRulesConfig(rx_interes_confirmado="(sin cerrar")
    assert config.validar() is not None


def test_validar_ok_con_defaults():
    assert CampanaRulesConfig().validar() is None


def test_compile_rules_normaliza_botones_sin_tildes_ni_mayusculas():
    config = CampanaRulesConfig(boton_cupo="¡Quiero Mi Cupó!")
    compiled = compile_rules(config)
    assert compiled.boton_cupo == "quiero mi cupo"
    assert compiled.boton_cupo in compiled.botones


def test_compile_rules_cortesias_normalizadas():
    config = CampanaRulesConfig(cortesias=("Hola", "GRACIAS"))
    compiled = compile_rules(config)
    assert "hola" in compiled.cortesias
    assert "gracias" in compiled.cortesias


def test_es_ignorable_detecta_digito_de_encuesta():
    compiled = compile_rules(CampanaRulesConfig())
    assert compiled.es_ignorable("3") is True
    assert compiled.es_ignorable("Los intereses") is False
