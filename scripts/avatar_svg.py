#!/usr/bin/env python3
"""
Mommy Avatar SVG Generator

Creates stylized SVG avatars for the Mommy Bot persona with 4 expressions:
- neutral: Calm, confident, slight smile
- pleased: Warm smile, bright eyes
- concerned: Slight frown, alert expression
- skeptical: Raised eyebrow, knowing smirk

Design: Modern, fashion-illustration aesthetic with teal accents.
"""

from typing import Literal

AvatarState = Literal["neutral", "pleased", "concerned", "skeptical"]


def get_avatar_svg(state: AvatarState = "neutral", size: int = 80) -> str:
    """
    Generate inline SVG for Mommy avatar in specified state.

    Args:
        state: One of 'neutral', 'pleased', 'concerned', 'skeptical'
        size: Width/height in pixels (SVG scales perfectly)

    Returns:
        Complete SVG string ready for HTML embedding
    """

    # Expression-specific elements (eyes and mouth)
    expressions = {
        "neutral": _get_neutral_expression(),
        "pleased": _get_pleased_expression(),
        "concerned": _get_concerned_expression(),
        "skeptical": _get_skeptical_expression(),
    }

    expression = expressions.get(state, expressions["neutral"])

    svg = f'''<svg width="{size}" height="{size}" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="hairGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1A2744"/>
      <stop offset="100%" style="stop-color:#0D1B2A"/>
    </linearGradient>
    <linearGradient id="skinGradient" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FDF2E9"/>
      <stop offset="100%" style="stop-color:#E8D5C4"/>
    </linearGradient>
    <linearGradient id="tealGradient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4FD1C5"/>
      <stop offset="100%" style="stop-color:#38B2AC"/>
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-opacity="0.15"/>
    </filter>
  </defs>

  <!-- Background circle -->
  <circle cx="40" cy="40" r="38" fill="#111D2E"/>

  <!-- Hair back layer -->
  <path d="M15 35 Q12 20 25 12 Q40 5 55 12 Q68 20 65 35
           Q68 50 60 60 L58 48 Q55 35 40 32 Q25 35 22 48 L20 60
           Q12 50 15 35"
        fill="url(#hairGradient)"/>

  <!-- Neck -->
  <path d="M32 58 L32 70 Q40 72 48 70 L48 58" fill="url(#skinGradient)"/>

  <!-- Face shape -->
  <ellipse cx="40" cy="42" rx="20" ry="24" fill="url(#skinGradient)" filter="url(#softShadow)"/>

  <!-- Hair front/bangs -->
  <path d="M20 38 Q22 28 30 24 Q40 20 50 24 Q58 28 60 38
           Q58 32 50 30 Q40 28 30 30 Q22 32 20 38"
        fill="url(#hairGradient)"/>

  <!-- Teal earrings (signature element) -->
  <circle cx="18" cy="50" r="4" fill="url(#tealGradient)">
    <animate attributeName="opacity" values="0.9;1;0.9" dur="3s" repeatCount="indefinite"/>
  </circle>
  <circle cx="62" cy="50" r="4" fill="url(#tealGradient)">
    <animate attributeName="opacity" values="0.9;1;0.9" dur="3s" repeatCount="indefinite"/>
  </circle>

  <!-- Expression (eyes, eyebrows, mouth) -->
  {expression}

  <!-- Subtle blush -->
  <ellipse cx="28" cy="48" rx="5" ry="3" fill="#E8B4B8" opacity="0.3"/>
  <ellipse cx="52" cy="48" rx="5" ry="3" fill="#E8B4B8" opacity="0.3"/>

  <!-- Teal accent in hair -->
  <path d="M25 30 Q30 28 32 32" stroke="#4FD1C5" stroke-width="1.5" fill="none" opacity="0.6"/>

</svg>'''

    return svg


def _get_neutral_expression() -> str:
    """Calm, confident expression with slight smile."""
    return '''
  <!-- Eyes - neutral, attentive -->
  <ellipse cx="32" cy="40" rx="3.5" ry="4" fill="#2D3748"/>
  <ellipse cx="48" cy="40" rx="3.5" ry="4" fill="#2D3748"/>
  <circle cx="33" cy="39" r="1.2" fill="white" opacity="0.8"/>
  <circle cx="49" cy="39" r="1.2" fill="white" opacity="0.8"/>

  <!-- Eyebrows - relaxed -->
  <path d="M26 34 Q32 32 38 34" stroke="#1A2744" stroke-width="1.5" fill="none" stroke-linecap="round"/>
  <path d="M42 34 Q48 32 54 34" stroke="#1A2744" stroke-width="1.5" fill="none" stroke-linecap="round"/>

  <!-- Mouth - slight knowing smile -->
  <path d="M34 54 Q40 58 46 54" stroke="#C17F7F" stroke-width="2" fill="none" stroke-linecap="round"/>
'''


def _get_pleased_expression() -> str:
    """Warm, genuine smile with bright eyes."""
    return '''
  <!-- Eyes - happy, slightly closed -->
  <path d="M28 40 Q32 37 36 40" stroke="#2D3748" stroke-width="2.5" fill="none" stroke-linecap="round"/>
  <path d="M44 40 Q48 37 52 40" stroke="#2D3748" stroke-width="2.5" fill="none" stroke-linecap="round"/>

  <!-- Eyebrows - raised, happy -->
  <path d="M26 32 Q32 29 38 32" stroke="#1A2744" stroke-width="1.5" fill="none" stroke-linecap="round"/>
  <path d="M42 32 Q48 29 54 32" stroke="#1A2744" stroke-width="1.5" fill="none" stroke-linecap="round"/>

  <!-- Mouth - big warm smile -->
  <path d="M32 52 Q40 60 48 52" stroke="#C17F7F" stroke-width="2.5" fill="none" stroke-linecap="round"/>

  <!-- Extra sparkle in eyes area -->
  <circle cx="32" cy="38" r="1" fill="#4FD1C5" opacity="0.5"/>
  <circle cx="48" cy="38" r="1" fill="#4FD1C5" opacity="0.5"/>
'''


def _get_concerned_expression() -> str:
    """Slight frown, alert and watchful."""
    return '''
  <!-- Eyes - wider, alert -->
  <ellipse cx="32" cy="40" rx="4" ry="5" fill="#2D3748"/>
  <ellipse cx="48" cy="40" rx="4" ry="5" fill="#2D3748"/>
  <circle cx="33" cy="39" r="1.5" fill="white" opacity="0.9"/>
  <circle cx="49" cy="39" r="1.5" fill="white" opacity="0.9"/>

  <!-- Eyebrows - furrowed, concerned -->
  <path d="M26 33 Q32 35 38 33" stroke="#1A2744" stroke-width="1.8" fill="none" stroke-linecap="round"/>
  <path d="M42 33 Q48 35 54 33" stroke="#1A2744" stroke-width="1.8" fill="none" stroke-linecap="round"/>

  <!-- Mouth - slight frown -->
  <path d="M34 56 Q40 53 46 56" stroke="#C17F7F" stroke-width="2" fill="none" stroke-linecap="round"/>

  <!-- Worry line -->
  <path d="M38 30 L42 30" stroke="#D4A59A" stroke-width="0.8" opacity="0.4"/>
'''


def _get_skeptical_expression() -> str:
    """Raised eyebrow, knowing smirk - 'are you sure about that?'"""
    return '''
  <!-- Eyes - one slightly narrowed -->
  <ellipse cx="32" cy="40" rx="3.5" ry="4" fill="#2D3748"/>
  <ellipse cx="48" cy="41" rx="3" ry="3" fill="#2D3748"/>
  <circle cx="33" cy="39" r="1.2" fill="white" opacity="0.8"/>
  <circle cx="49" cy="40" r="1" fill="white" opacity="0.8"/>

  <!-- Eyebrows - one raised (skeptical) -->
  <path d="M26 34 Q32 32 38 34" stroke="#1A2744" stroke-width="1.5" fill="none" stroke-linecap="round"/>
  <path d="M42 31 Q48 28 54 32" stroke="#1A2744" stroke-width="1.8" fill="none" stroke-linecap="round"/>

  <!-- Mouth - knowing smirk (asymmetric) -->
  <path d="M34 54 Q38 55 42 54 Q46 56 48 55" stroke="#C17F7F" stroke-width="2" fill="none" stroke-linecap="round"/>
'''


def get_avatar_with_container(state: AvatarState = "neutral", size: int = 80) -> str:
    """
    Get avatar SVG wrapped in a styled container div.

    Args:
        state: Avatar expression state
        size: Size in pixels

    Returns:
        HTML string with container and SVG
    """
    svg = get_avatar_svg(state, size)

    html = f'<div class="mommy-avatar-container" style="width: {size}px; height: {size}px; margin: 0 auto;">'
    html += svg
    html += '</div>'

    return html


# ─── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Mommy Avatar SVG Generator")
    print("=" * 50)

    for state in ["neutral", "pleased", "concerned", "skeptical"]:
        svg = get_avatar_svg(state)
        print(f"\n{state.upper()}: {len(svg)} characters")

    # Write test HTML file
    test_html = """<!DOCTYPE html>
<html>
<head>
    <title>Mommy Avatar Test</title>
    <style>
        body { background: #0A1628; padding: 40px; font-family: sans-serif; }
        .container { display: flex; gap: 40px; justify-content: center; flex-wrap: wrap; }
        .avatar-box { text-align: center; }
        .label { color: #A0AEC0; margin-top: 12px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
"""
    for state in ["neutral", "pleased", "concerned", "skeptical"]:
        test_html += f'<div class="avatar-box">{get_avatar_svg(state, 120)}<div class="label">{state}</div></div>\n'

    test_html += """
    </div>
</body>
</html>"""

    print("\n\nTest HTML written. Copy the output above to preview avatars.")
