from recetary import db, repo
from recetary.models import RecipeCreate, StepIn


def _recipe(source_ref: str, title: str) -> RecipeCreate:
    return RecipeCreate(
        title=title,
        source_type="video",
        source_ref=source_ref,
        steps=[StepIn(text="paso")],
    )


def test_one_recipe_platform_rejects_url_variants(temp_db):
    with db.get_conn() as conn:
        first = repo.create_recipe(
            conn,
            _recipe(
                "https://www.instagram.com/reel/DdYem-CstWf/",
                "Arroz de Instagram",
            ),
        )
        try:
            repo.create_recipe(
                conn,
                _recipe(
                    "https://www.instagram.com/inigoisaosakai/reel/DdYem-CstWf/",
                    "Duplicada",
                ),
            )
        except repo.DuplicateSourceError as error:
            assert error.recipe_id == first
            assert error.title == "Arroz de Instagram"
        else:
            raise AssertionError("duplicate Instagram source was accepted")


def test_youtube_source_can_have_multiple_recipes(temp_db):
    with db.get_conn() as conn:
        first = repo.create_recipe(
            conn,
            _recipe("https://www.youtube.com/watch?v=AbCdEfGhIjK", "Primera"),
        )
        second = repo.create_recipe(
            conn,
            _recipe("https://youtu.be/AbCdEfGhIjK", "Segunda"),
        )
    assert first != second
