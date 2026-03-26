<script setup lang="ts">
import { QuillEditor } from '@vueup/vue-quill'
import '@vueup/vue-quill/dist/vue-quill.snow.css'

const model = defineModel<string>({ default: '' })

withDefaults(
  defineProps<{
    placeholder?: string
    minHeight?: string
  }>(),
  {
    placeholder: '请输入活动内容',
    minHeight: '220px',
  },
)

const toolbar = [
  ['bold', 'italic', 'underline'],
  [{ header: [2, 3, false] }],
  [{ list: 'ordered' }, { list: 'bullet' }],
  [{ color: [] }, { background: [] }],
  ['blockquote', 'code-block'],
  ['link'],
  ['clean'],
]
</script>

<template>
  <div class="rich-text-editor">
    <QuillEditor
      v-model:content="model"
      content-type="html"
      theme="snow"
      :toolbar="toolbar"
      :placeholder="placeholder"
    />
  </div>
</template>

<style scoped>
.rich-text-editor :deep(.ql-container) {
  border-radius: 0 0 18px 18px;
  min-height: v-bind(minHeight);
  background: rgba(255, 255, 255, 0.9);
}

.rich-text-editor :deep(.ql-toolbar) {
  border-radius: 18px 18px 0 0;
  background: rgba(255, 255, 255, 0.9);
}

.rich-text-editor :deep(.ql-editor) {
  min-height: v-bind(minHeight);
}
</style>
