export const resourceStubs = {
  'el-card': {
    template: '<div><slot name="header" /><slot /></div>'
  },
  'el-table': {
    props: ['data'],
    provide() {
      return { getTableData: () => this.data }
    },
    template: '<div class="table"><slot /></div>'
  },
  'el-table-column': {
    inject: ['getTableData'],
    props: ['prop', 'label', 'width', 'minWidth'],
    template:
      '<div class="column"><div v-for="row in getTableData()" :key="row.id || row.date"><slot :row="row">{{ row[prop] }}</slot></div></div>'
  },
  'el-pagination': { template: '<div />' },
  'el-row': { template: '<div class="row"><slot /></div>' },
  'el-col': { props: ['span'], template: '<div class="col"><slot /></div>' },
  'el-tooltip': { template: '<span><slot /></span>' },
  'el-image': { props: ['src'], template: '<img :src="src" />' },
  'el-dialog': {
    props: ['modelValue', 'title', 'width'],
    template:
      '<div v-if="modelValue" class="dialog"><h2>{{ title }}</h2><slot /><slot name="footer" /></div>'
  },
  'el-form': {
    methods: {
      validate: () => Promise.resolve(true),
      validateField: () => Promise.resolve(true)
    },
    template: '<form><slot /></form>'
  },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    props: ['modelValue', 'placeholder', 'type', 'disabled', 'maxlength', 'showWordLimit'],
    emits: ['update:modelValue'],
    template:
      '<input :type="type || \'text\'" :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-input-number': {
    props: ['modelValue', 'min', 'max'],
    emits: ['update:modelValue'],
    template:
      '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />'
  },
  'el-select': {
    props: ['modelValue', 'disabled', 'placeholder', 'clearable'],
    emits: ['update:modelValue', 'change'],
    methods: {
      onChange(event) {
        const raw = event.target.value
        const isNumeric = raw !== '' && !Number.isNaN(Number(raw))
        const value = raw === '' ? undefined : isNumeric ? Number(raw) : raw
        this.$emit('update:modelValue', value)
        this.$emit('change')
      }
    },
    template:
      '<select :value="modelValue" :disabled="disabled" @change="onChange"><slot /></select>'
  },
  'el-option': {
    props: ['label', 'value'],
    template: '<option :value="value">{{ label }}</option>'
  },
  'el-time-picker': {
    props: ['modelValue', 'placeholder', 'disabled', 'format', 'valueFormat', 'editable'],
    emits: ['update:modelValue', 'change'],
    template:
      '<input :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" @change="$emit(\'change\')" />'
  },
  'el-date-picker': {
    props: ['modelValue', 'placeholder', 'disabled', 'format', 'valueFormat', 'disabledDate'],
    emits: ['update:modelValue'],
    template:
      '<input :value="modelValue" :placeholder="placeholder" :disabled="disabled" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-upload': { template: '<div><slot /></div>' },
  'el-radio-group': { template: '<div><slot /></div>' },
  'el-radio': { template: '<div><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-button': {
    props: ['disabled', 'loading', 'text', 'bg', 'type'],
    emits: ['click'],
    template:
      '<button type="button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
  },
  'el-empty': { template: '<div class="empty">暂无数据</div>' },
  'el-drawer': {
    props: ['modelValue', 'title'],
    template:
      '<div v-if="modelValue" class="drawer"><h2>{{ title }}</h2><slot /></div>'
  },
  'el-timeline': { template: '<div class="timeline"><slot /></div>' },
  'el-timeline-item': {
    props: ['timestamp', 'type'],
    template:
      '<div class="timeline-item"><span>{{ timestamp }}</span><slot /></div>'
  },
  'el-switch': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />'
  },
  'el-badge': {
    props: ['value', 'max'],
    template: '<span class="badge"><slot /><span>{{ value }}</span></span>'
  },
  'el-icon': { template: '<span><slot /></span>' }
}

export function findButton(root, text) {
  return root.findAll('button').find((button) => button.text() === text)
}

export function findDialog(wrapper) {
  return wrapper.find('.dialog')
}
