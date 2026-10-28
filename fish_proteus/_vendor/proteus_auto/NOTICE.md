# Source provenance

Adapted MIT source from kudoumakoto6523-design/Proteus_automatic_package,
commit 7439819a7ea4cff47fb9b321d8b0e97ac74fafb2. See LICENSE.upstream.

Only original Python runtime/format modules are included. Proprietary programs,
models, device definitions, official samples, firmware binaries and artifacts
are excluded. Experimental clone/swap demo helpers are not public dependencies.

Local modifications start with package-relative imports. Configuration and
8.17 compatibility changes are recorded separately by the Fish implementation;
upstream 8.16 native tests are not evidence that this adapted source works on 8.17.

The component codec also restores a requested, previously imported embedded
definition lazily after a save/reopen, sharing the existing validated template
constructor. Definitions are not overwritten or reimported, unused definitions
are not eagerly parsed, and a rejected add does not change the template cache.
