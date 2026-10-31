#!/usr/bin/env python3
"""Install the local Codex integration without relying on plugin-hook discovery.

Codex 0.162.1 discovers installed plugin Skills but does not execute their
bundled hooks. Register the same hooks at user level and standalone command
Skills instead. The installed scripts are self-contained and remain available
after this build folder moves. Existing unrelated hooks are preserved.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

OWNER = 'ConsoleX delivery checks'
# The task tool service, as a Codex MCP server in config.toml. Only this block is ever written or removed.
MCP_BEGIN = '# BEGIN ConsoleX task tools (managed by the ConsoleX installer; do not edit)'
MCP_END = '# END ConsoleX task tools'
MCP_BLOCK = re.compile(r'\n?%s\n.*?%s\n?' % (re.escape(MCP_BEGIN), re.escape(MCP_END)), re.S)
MCP_TABLE = re.compile(r'^\s*\[\s*mcp_servers\s*\.\s*"?consolex"?\s*[\].]', re.M)


def _toml_string(value):
    return json.dumps(str(value))  # a JSON string is a valid TOML basic string


def mcp_config(text, script):
    """config.toml with the ConsoleX MCP server block replaced (or removed when `script` is None)."""
    text = MCP_BLOCK.sub('\n', text).rstrip('\n')
    if script is None:
        return text + '\n' if text else ''
    if MCP_TABLE.search(text):
        raise ValueError('config.toml already defines an MCP server named consolex; nothing changed')
    block = '\n'.join([MCP_BEGIN, '[mcp_servers.consolex]', 'command = "python3"', 'args = [%s]' % _toml_string(script),
                       'env = { CONSOLEX_RUNTIME = "codex" }', 'startup_timeout_sec = 20', 'tool_timeout_sec = 330',
                       # Codex refuses (never prompts) an MCP call that needs approval under "never" (Full access).
                       # The owner's consent is the computer's "Tools and files" permission in ConsoleX.
                       'default_tools_approval_mode = "approve"', MCP_END])
    updated = (text + '\n\n' if text else '') + block + '\n'
    try:
        import tomllib
    except ImportError:  # Python < 3.11: the block is fixed text and the rest is untouched
        return updated
    try:
        tomllib.loads(updated)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError('config.toml could not be read (%s); nothing changed' % exc)
    return updated


def _write_text(path, text, prefix):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=prefix, suffix=path.suffix)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(text)
    os.replace(temporary, path)


def uninstall(codex_home, skills_dir, data_dir):
    codex_home, skills_dir, data_dir = map(lambda p: Path(p).expanduser().resolve(), (codex_home, skills_dir, data_dir))
    config_path = codex_home / 'hooks.json'
    if config_path.exists():
        config = json.loads(config_path.read_text())
        for event, groups in list(config.get('hooks', {}).items()):
            kept = []
            for group in groups:
                handlers = [item for item in group.get('hooks', []) if item.get('statusMessage') != OWNER]
                if handlers:
                    kept.append({**group, 'hooks': handlers})
            if kept:
                config['hooks'][event] = kept
            else:
                config['hooks'].pop(event, None)
        fd, temporary = tempfile.mkstemp(dir=codex_home, prefix='.consolex-hooks-', suffix='.json')
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        os.replace(temporary, config_path)
    toml_path = codex_home / 'config.toml'
    if toml_path.exists() and MCP_BLOCK.search(toml_path.read_text(encoding='utf-8')):
        _write_text(toml_path, mcp_config(toml_path.read_text(encoding='utf-8'), None), '.consolex-config-')
    for skill in skills_dir.glob('consolex-*'):
        if skill.is_dir() and (skill / '.consolex-owned').is_file():
            shutil.rmtree(skill)
    target = data_dir / 'codex-integration'
    if (target / '.consolex-owned').is_file():
        shutil.rmtree(target)


def install(codex_home, skills_dir, data_dir):
    source = Path(__file__).resolve().parent / 'plugins/consolex'
    if not (source / 'scripts/consolex_core.py').is_file():
        raise ValueError('Build first: python3 integrations/coding_agents/build.py')
    codex_home, skills_dir, data_dir = map(lambda p: Path(p).expanduser().resolve(), (codex_home, skills_dir, data_dir))
    target = data_dir / 'codex-integration'
    if target == source or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('Install destination must be outside the distribution')
    config_path = codex_home / 'hooks.json'
    existing = json.loads(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(existing, dict) or not isinstance(existing.get('hooks', {}), dict):
        raise ValueError('Existing hooks.json is invalid; nothing changed')
    for groups in existing.get('hooks', {}).values():
        if not isinstance(groups, list) or any(not isinstance(group, dict) or
                not isinstance(group.get('hooks', []), list) or
                any(not isinstance(handler, dict) for handler in group.get('hooks', [])) for group in groups):
            raise ValueError('Existing hook groups are invalid; nothing changed')
    toml_path = codex_home / 'config.toml'
    toml_text = toml_path.read_text(encoding='utf-8') if toml_path.exists() else ''
    toml_updated = mcp_config(toml_text, target / 'scripts/consolex_mcp.py')  # refuses before anything is written
    # Validate collisions before writing anything. Only replace our own Skills.
    for skill in (source / 'skills').iterdir():
        destination = skills_dir / skill.name
        if destination.exists() and not (destination / '.consolex-owned').is_file():
            raise ValueError('Refusing to replace an existing Skill: %s' % destination)
    if target.exists() and not (target / '.consolex-owned').is_file():
        raise ValueError('Refusing to replace an unowned integration directory')
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (target / '.consolex-owned').write_text(OWNER)
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in (source / 'skills').iterdir():
        destination = skills_dir / skill.name
        shutil.copytree(skill, destination, dirs_exist_ok=True)
        (destination / '.consolex-owned').write_text(OWNER)
    hooks = json.loads((source / 'hooks/hooks.json').read_text())['hooks']
    installed = existing.setdefault('hooks', {})
    for event, groups in hooks.items():
        preserved = []
        for group in installed.get(event, []):
            handlers = [handler for handler in group.get('hooks', []) if handler.get('statusMessage') != OWNER]
            if handlers:
                preserved.append({**group, 'hooks': handlers})
        import shlex
        import subprocess
        script = str(target / 'scripts/consolex.py')
        command = subprocess.list2cmdline(['python3', script]) if os.name == 'nt' else 'python3 ' + shlex.quote(script)
        for group in groups:
            for handler in group['hooks']:
                handler['command'] = command
                handler['statusMessage'] = OWNER
        installed[event] = preserved + groups
    codex_home.mkdir(parents=True, exist_ok=True)
    if config_path.exists():
        # A fixed first-install backup is never overwritten by upgrades.
        backup = codex_home / 'hooks.before-consolex.json'
        if not backup.exists():
            shutil.copy2(config_path, backup)
    fd, temporary = tempfile.mkstemp(dir=codex_home, prefix='.consolex-hooks-', suffix='.json')
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        json.dump(existing, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    os.replace(temporary, config_path)
    if toml_updated != toml_text:
        if toml_path.exists() and not (codex_home / 'config.before-consolex.toml').exists():
            shutil.copy2(toml_path, codex_home / 'config.before-consolex.toml')
        _write_text(toml_path, toml_updated, '.consolex-config-')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME') or str(Path.home() / '.codex'))
    parser.add_argument('--skills-dir', default=str(Path.home() / '.agents/skills'))
    parser.add_argument('--data-dir', default=os.environ.get('CONSOLEX_HOME') or str(Path.home() / '.consolex'))
    parser.add_argument('--uninstall', action='store_true', help='Remove only ConsoleX-owned hooks and Skills; keep shared sign-in')
    args = parser.parse_args()
    try:
        (uninstall if args.uninstall else install)(args.codex_home, args.skills_dir, args.data_dir)
    except (ValueError, OSError) as exc:
        parser.exit(1, 'ConsoleX installation failed: %s\n' % exc)
    print('ConsoleX integration removed; restart Codex. Shared sign-in was kept.' if args.uninstall else
          'ConsoleX installed. Restart Codex, review and trust the ConsoleX hooks in /hooks, then run $consolex-login.')
