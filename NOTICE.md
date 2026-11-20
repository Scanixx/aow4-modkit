# Provenance and distribution status

This is an unofficial toolkit for Age of Wonders 4. Preview 0.1.0a4 is prepared
locally and has not been published.
Version [0.1.0a3](https://github.com/Scanixx/aow4-modkit/releases/tag/v0.1.0a3) was published on November 20, 2026.
Repository: [Scanixx/aow4-modkit](https://github.com/Scanixx/aow4-modkit). It is not affiliated with or endorsed by Triumph Studios or Paradox.

The implementation is extracted and rewritten from locally authored tools used
for Donate Spell and More Secret Ascension Skills. It does not import those
projects or require their archives, UUIDs, research files or installed copies.

Small binary framing constants describe observed serializers. Content catalogs
contain resource identifiers, descriptive names and link metadata, not resource
payloads, game executables, textures, or other authors' packages.

AI assisted implementation and documentation. No AI-generated artwork is
included. The first example contains no artwork.

The toolkit's authored code and documentation are licensed under the MIT
License. See [LICENSE](LICENSE) for the complete terms and copyright notice.
This license does not grant rights to the game, its artwork, or other authors'
mods. Those remain subject to their respective owners' terms.

## Intended conversion workflow

RPK-to-Python conversion helps mod authors migrate their own existing projects
and continue maintaining them with ModKit. It can also support a project that
you maintain with its author's permission. Retain the original credits and
license notices when adapting an authorized project. Generated Python remains
a representation of the input mod; conversion does not transfer ownership or
grant permission to redistribute its content. The MIT license covers ModKit
code and documentation, separately from any mod processed by the tool.
