import typer

app = typer.Typer(help="Book Store Assistant CLI.")


@app.command()
def main() -> None:
    """Describe the current project status."""
    typer.echo("Book Store Assistant CLI is ready.")
