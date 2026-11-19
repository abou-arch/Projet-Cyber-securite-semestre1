import matplotlib
import pytest

matplotlib.use("Agg")  # pas d'écran pendant les tests

from malware_family.figures import FIGURES_DIR, family_colors, new_figure, save_figure  # noqa: E402


def test_save_figure_follows_naming_convention(tmp_path):
    fig, ax = new_figure()
    ax.plot([0, 1], [1, 0])
    path = save_figure(fig, "A_essai_01", directory=tmp_path)
    assert path == tmp_path / "A_essai_01.png"
    assert path.read_bytes().startswith(b"\x89PNG")
    for bad in ("essai", "D_essai", "A_Essai", "A_effectifs familles", "A_entropie_é"):
        with pytest.raises(ValueError, match="préfixe A_, B_ ou C_"):
            save_figure(fig, bad, directory=tmp_path)
    assert FIGURES_DIR.parts[-2:] == ("results", "figures")


@pytest.mark.parametrize("n", [3, 10, 20])
def test_family_colors_are_distinct_and_stable(n):
    families = [f"famille{i}" for i in range(n)]
    colors = family_colors(families)
    assert list(colors) == families
    assert len(set(colors.values())) == n
    assert family_colors(families) == colors  # mêmes couleurs pour A, B et C


def test_project_palette_is_the_default():
    """Palette du projet (violets, ors, beiges, gris) : C0 = violet, C1 = or, échelles enregistrées."""
    from matplotlib.colors import to_hex

    from malware_family import figures

    fig, ax = new_figure()
    line, = ax.plot([0, 1], [0, 1])
    assert to_hex(line.get_color()) == figures.VIOLET.lower()
    assert to_hex(matplotlib.rcParams["axes.prop_cycle"].by_key()["color"][1]) == figures.GOLD.lower()
    for name in ("projet_seq", "projet_div"):
        assert name in matplotlib.colormaps
    assert matplotlib.rcParams["image.cmap"] == "projet_seq"
    assert set(figures.palette(10)) <= set(figures.FAMILY_PALETTE)
    assert figures.text_color_on("projet_seq", 0.0) == "black"   # beige pâle : texte noir
    assert figures.text_color_on("projet_seq", 1.0) == "white"   # violet foncé : texte blanc
