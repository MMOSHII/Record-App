import { defineComponent, h } from 'vue'

export default defineComponent({
  name: 'ChatMessageList',
  props: {
    messages: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false }
  },
  setup(props) {
    return () =>
      h('div', { class: 'flex-1 overflow-y-auto p-5 space-y-3 min-h-[120px]' }, [
        ...((props.messages || []).length
          ? (props.messages || []).map((msg, idx) =>
              h('div', { key: `${msg.message_id || idx}`, class: ['flex', msg.role === 'user' ? 'justify-end' : 'justify-start'] }, [
                h(
                  'div',
                  {
                    class: [
                      'max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm whitespace-pre-wrap break-words',
                      msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-br-sm'
                        : 'bg-slate-100 text-slate-800 rounded-bl-sm'
                    ]
                  },
                  msg.content || ''
                )
              ])
            )
          : [h('p', { class: 'text-xs text-slate-400 text-center py-8' }, 'Start a conversation about this transcript.')]),
        props.loading
          ? h('p', { class: 'text-xs text-slate-400' }, 'AI is responding…')
          : null
      ])
  }
})

