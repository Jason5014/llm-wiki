import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/kb' },
    {
      path: '/kb',
      name: 'KBHome',
      component: () => import('../views/HomeView.vue'),
      meta: { title: '知识库管理' },
    },
    {
      path: '/kb/:kbId/wiki',
      name: 'Wiki',
      component: () => import('../views/WikiView.vue'),
      meta: { title: 'Wiki 浏览' },
    },
    {
      path: '/kb/:kbId/wiki/:pageType/:name',
      name: 'WikiPage',
      component: () => import('../views/WikiView.vue'),
      meta: { title: 'Wiki 页面' },
    },
    {
      path: '/kb/:kbId/search',
      name: 'Search',
      component: () => import('../views/SearchView.vue'),
      meta: { title: '搜索问答' },
    },
    {
      path: '/kb/:kbId/graph',
      name: 'Graph',
      component: () => import('../views/GraphView.vue'),
      meta: { title: '知识图谱' },
    },
    {
      path: '/kb/:kbId/pipeline',
      name: 'Pipeline',
      component: () => import('../views/PipelineView.vue'),
      meta: { title: '流水线管理' },
    },
    {
      path: '/kb/:kbId/docs',
      name: 'Documents',
      component: () => import('../views/DocumentsView.vue'),
      meta: { title: '原始文档' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title || 'LLM Wiki'} — LLM Wiki`
})

export default router
