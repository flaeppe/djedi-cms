import cio
import six
import textwrap
from django import template
from django.template import TemplateSyntaxError
from .template import register
from ..compat import parse_bits


def render_node(node, context=None, edit=True):
    """
    Render node as html for templates, with edit tagging.
    """
    output = node.render(**context or {}) or u''
    if edit:
        return u'<span data-i18n="{0}">{1}</span>'.format(node.uri.clone(scheme=None, ext=None, version=None), output)
    else:
        return output


@register.lazy_tag
def node(key, default=None, edit=True):
    """
    Simple node tag:
    {% node 'page/title' default='Lorem ipsum' edit=True %}
    """
    node = cio.get(key, default=default or u'')
    return lambda _: render_node(node, edit=edit)


class BlockNode(template.Node):
    """
    Block node tag using body content as default:
    {% blocknode 'page/title' edit=True %}
        Lorem ipsum
    {% endblocknode %}
    """
    @classmethod
    def tag(cls, parser, token):
        # Parse tag args and kwargs
        bits = token.split_contents()[1:]
        params = ('uri', 'edit')
        args, kwargs = parse_bits(parser, bits, params, None, True, (True,), None, 'blocknode')

        # Assert uri is the only tag arg
        if len(args) > 1:
            raise TemplateSyntaxError('Malformed arguments to blocknode tag')

        # Resolve uri variable
        try:
            uri = args[0].resolve({})
        except AttributeError:
            # URI is not resolvable at this moment, which implies that it is
            # probably a variable.
            uri = None

        # Parse tag body (default content)
        tokens = parser.parse(('endblocknode',))
        parser.delete_first_token()  # Remove endblocknode tag

        # Render default content tokens and dedent common leading whitespace
        default = u''.join((token.render({}) for token in tokens))
        default = default.strip('\n\r')
        default = textwrap.dedent(default)

        # Get node for uri, lacks context variable lookup due to lazy loading.
        node = cio.get(uri, default) if uri is not None else None

        return cls(tokens, node, default, args, kwargs)

    def __init__(self, tokens, node, default, args, kwargs):
        self.tokens = tokens
        self.node = node
        self.default = default
        self.args = args
        self.kwargs = kwargs

    def render(self, context):
        # Check if the node is defined. If not, it probably was a variable
        # and could not be resolved at that time. Resolve it now that the context
        # is available.
        if self.node is not None:
            node = self.node
        else:
            uri = self.args[0].resolve(context)
            node = cio.get(uri, self.default)

        # Resolve tag kwargs against context
        resolved_kwargs = dict((key, value.resolve(context)) for key, value in six.iteritems(self.kwargs))
        edit = resolved_kwargs.pop('edit', True)

        return render_node(node, context=resolved_kwargs, edit=edit)


register.tag('blocknode', BlockNode.tag)
