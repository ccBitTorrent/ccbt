"""Demo script for splash screen with 90+ second animation sequence.

Demonstrates the splash screen with various background animations and color transitions.
"""

from __future__ import annotations

import asyncio
import sys
import os

# Handle Unicode encoding for Windows
if os.name == 'nt':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.live import Live
except ImportError:
    print("Rich library is required. Install with: pip install rich")
    sys.exit(1)

# Import splash screen
try:
    from .splash_screen import SplashScreen, run_splash_screen
except ImportError:
    # Fallback: direct import
    import sys
    from pathlib import Path
    
    splash_dir = Path(__file__).parent
    if str(splash_dir) not in sys.path:
        sys.path.insert(0, str(splash_dir))
    
    from splash_screen import SplashScreen, run_splash_screen


async def demo_rich_console() -> None:
    """Demo splash screen with Rich Console (CLI mode)."""
    console = Console()
    
    console.print("\n" + "=" * 80)
    console.print("Splash Screen Demo - Rich Console Mode")
    console.print("=" * 80)
    console.print("\nThis demo will run for 90 seconds with various background animations")
    console.print("and color transitions. Press Ctrl+C to stop early.\n")
    console.print("=" * 80 + "\n")
    
    try:
        # Create splash screen
        console.print("[dim]Creating splash screen...[/dim]")
        splash = SplashScreen(console=console, duration=90.0)
        console.print(f"[green]✓ Splash screen created with {len(splash.sequence.animations)} animation segments[/green]\n")
        
        # Run the animation (executor handles Live internally)
        console.print("[yellow]Starting animation...[/yellow]\n")
        await splash.run()
        console.print("\n[green]✓ Animation completed![/green]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        raise


async def main() -> None:
    """Main entry point."""
    try:
        await demo_rich_console()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nDemo cancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

