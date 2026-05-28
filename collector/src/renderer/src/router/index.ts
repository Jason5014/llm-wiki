import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/browser',
    },
    {
      path: '/browser',
      name: 'Browser',
      component: () => import('../views/BrowserView.vue'),
      meta: { title: '内嵌浏览器' },
    },
    {
      path: '/queue',
      name: 'Queue',
      component: () => import('../views/QueueView.vue'),
      meta: { title: '采集队列' },
    },
    {
      path: '/import',
      name: 'Import',
      component: () => import('../views/ImportView.vue'),
      meta: { title: '文件导入' },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { title: '设置' },
    },
  ],
})

export default router
