import{A as t}from"./api_publicComponent.c4201f33.js";import e from"./taskLog.165f009c.js";import{n as i}from"./index.61d8a2ac.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const s={};var a=i({name:"logInformation",inject:["reload"],components:{taskLog:e},props:{namecs:{required:!1}},data(){return{logtype:1,clusterList:[],filters:{stateSearch:"",typeSearch:"",taskName:"",taskBeginTime:"",taskEndTime:"",cluster_id:""},total:0,page:1,size:20,loading:!1,rows:[],taskTypeList:["ALL"],taskId:"",taskDetail:"",showTaskDetailVisible:!1,content:"",intervalID:"",needToFirstPage:!1,isTableshow:!0,startTime:{disabledDate:t=>{if(this.filters.taskEndTime)return t.getTime()>new Date(this.filters.taskEndTime).getTime()}},endTime:{disabledDate:t=>{if(this.filters.taskBeginTime)return t.getTime()<new Date(this.filters.taskBeginTime).getTime()}}}},watch:{$route:"fetchData","filters.searchKey"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)},"filters.typeSearch"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)},"filters.taskName"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)},"filters.taskBeginTime"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)},"filters.taskEndTime"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)}},methods:{checkboxChange(){this.needToFirstPage=!0,this.showList()},fetchData(t,e){console.log(e),console.log(t),this.$refs.pagination.internalCurrentPage=1,this.logtype=t.query.logtype,this.InitializationList()},handleSizeChange(t){this.size=t,this.total=0,this.needToFirstPage=!0,this.showList()},handleCurrentChange(t){this.page=t,this.showList()},handleSearch(){this.showList()},getTaskTypeList:function(){let e=this,i={task_class:this.logtype};e.loading=!0,t.getCbuTaskTypeList(i).then((function(t){e.loading=!1,e.taskTypeList=t,e.taskTypeList.unshift("ALL")}),(function(t){e.loading=!1}))},showList:function(){let e=this;this.needToFirstPage&&(this.page=1),1==this.page&&(this.total=0);let i={page_size:e.size,task_class:Number(e.logtype),page_num:e.page};""!==e.filters.stateSearch&&(i.state=e.filters.stateSearch),""!==e.filters.typeSearch&&(i.task_type=e.filters.typeSearch),e.filters.searchKey&&(i.search_key=e.filters.searchKey),e.filters.taskBeginTime&&(i.begin_create_time=e.filters.taskBeginTime),e.filters.taskEndTime&&(i.end_create_time=e.filters.taskEndTime),e.filters.cluster_id&&(i.cluster_id=e.filters.cluster_id),e.loading=!0,t.getTaskList(i).then((function(t){e.needToFirstPage=!1,e.loading=!1,t&&t.rows&&(e.total=t.total,e.rows=t.rows,e.isTableshow=!1,e.$nextTick((()=>{e.isTableshow=!0,e.$nextTick((()=>{e.$emit("btnHidden")}))})))}),(function(t){e.loading=!1}))},TaskDetailDialog:function(t,e){this.$nextTick((function(){this.$refs.tasklog.openDialog(e.task_id,"",1)}))},InitializationList(){const e=this;if(3!=e.logtype)e.getTaskTypeList(),e.loading=!0;else{e.taskTypeList=["ALL","failback","switch","failover","create_sr_cluster"],e.getTaskTypeList();const i={page_num:1,page_size:2e4};t.getClusterList(i).then((function(t){e.loading=!1,t&&t.rows&&(e.clusterList=t.rows,e.showList())}),(function(t){e.loading=!1}))}this.$nextTick(this.showList)}},mounted:function(){this.logtype=this.$route.query.logtype,this.InitializationList(),this.filters={stateSearch:"",typeSearch:"",taskName:"",taskBeginTime:"",taskEndTime:"",cluster_id:""}}},(function(){var t=this,e=t.$createElement,i=t._self._c||e;return i("el-row",[i("el-col",{attrs:{span:24}},[i("el-form",{staticClass:"demo-form-inline",staticStyle:{margin:"0"},attrs:{inline:!0,model:t.filters},nativeOn:{submit:function(t){t.preventDefault()}}},[i("el-form-item",{attrs:{label:t.$t("publicLogComponent.zhuang-tai")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:t.$t("publicLogComponent.zhuangtai-xuanze")},on:{change:t.checkboxChange},model:{value:t.filters.stateSearch,callback:function(e){t.$set(t.filters,"stateSearch",e)},expression:"filters.stateSearch"}},[i("el-option",{attrs:{label:"ALL",value:""}}),i("el-option",{attrs:{label:"Success",value:"1"}}),i("el-option",{attrs:{label:"Running",value:"0"}}),i("el-option",{attrs:{label:"Fault",value:"-1"}})],1)],1),i("el-form-item",{attrs:{label:t.$t("publicLogComponent.renwu-leixing")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:t.$t("publicLogComponent.renwuleixing-xuanze")},on:{change:t.checkboxChange},model:{value:t.filters.typeSearch,callback:function(e){t.$set(t.filters,"typeSearch",e)},expression:"filters.typeSearch"}},t._l(t.taskTypeList,(function(t,e){return i("el-option",{key:e,attrs:{label:t,value:"ALL"==t?"":t}})})),1)],1),3==t.logtype?i("el-form-item",{attrs:{label:t.$t("publicLogComponent.suoshu-jiqun")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:t.$t("publicLogComponent.jiqun-xuanze")},on:{change:t.checkboxChange},model:{value:t.filters.cluster_id,callback:function(e){t.$set(t.filters,"cluster_id",e)},expression:"filters.cluster_id"}},[i("el-option",{attrs:{label:"ALL",value:""}}),t._l(t.clusterList,(function(t,e){return i("el-option",{key:e,attrs:{label:t.cluster_name+"(id="+t.cluster_id+")",value:t.cluster_id}})}))],2)],1):t._e(),i("el-form-item",[i("el-input",{staticStyle:{width:"230px"},attrs:{placeholder:t.$t("publicLogComponent.sousuo-renwu-message")},nativeOn:{keyup:function(e){return!e.type.indexOf("key")&&t._k(e.keyCode,"enter",13,e.key,"Enter")?null:t.handleSearch(e)}},model:{value:t.filters.searchKey,callback:function(e){t.$set(t.filters,"searchKey",e)},expression:"filters.searchKey"}}),i("el-tooltip",{staticClass:"item",attrs:{effect:"dark",content:t.$t("Public.question"),placement:"top"}},[i("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1),i("el-form-item",[i("el-date-picker",{staticStyle:{width:"220px"},attrs:{type:"datetime",placeholder:t.$t("publicLogComponent.qingxuanze-kaishishijian"),"default-time":"","value-format":"yyyy-MM-dd HH:mm:ss","picker-options":t.startTime},model:{value:t.filters.taskBeginTime,callback:function(e){t.$set(t.filters,"taskBeginTime",e)},expression:"filters.taskBeginTime"}})],1),i("el-form-item",[i("el-date-picker",{staticStyle:{width:"220px"},attrs:{type:"datetime",placeholder:t.$t("publicLogComponent.qingxuanze-jieshushijian"),"default-time":"","value-format":"yyyy-MM-dd HH:mm:ss","picker-options":t.endTime},model:{value:t.filters.taskEndTime,callback:function(e){t.$set(t.filters,"taskEndTime",e)},expression:"filters.taskEndTime"}})],1),i("el-form-item",{staticStyle:{float:"right"}},[i("el-button",{attrs:{type:"primary",size:"medium"},on:{click:t.handleSearch}},[t._v(t._s(t.$t("dbList.shou-suo")))])],1)],1)],1),i("el-col",{attrs:{span:24}},[t.isTableshow?i("el-table",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{data:t.rows,border:"","element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[i("el-table-column",{attrs:{prop:"task_id",label:t.$t("publicLogComponent.renwu-ID"),align:"center",width:"80px"}}),i("el-table-column",{attrs:{prop:"state",label:t.$t("dbList.zhuang-tai"),"header-align":"center",align:"left",width:"100px"},scopedSlots:t._u([{key:"default",fn:function(e){return[1===e.row.state?i("i",{staticClass:"el-icon-success green"},[i("span",{staticClass:"statefont"},[t._v(" Success")])]):-1===e.row.state?i("i",{staticClass:"el-icon-success red"},[i("span",{staticClass:"statefont"},[t._v(" Fault")])]):0===e.row.state?i("i",{staticClass:"el-icon-success"},[i("span",{staticClass:"statefont"},[t._v(" running")])]):t._e()]}}],null,!1,505972830)}),3==t.logtype?i("el-table-column",{attrs:{prop:"cluster_id",label:t.$t("publicLogComponent.suoshu-jiqun-no"),align:"center",width:"80px"}}):t._e(),i("el-table-column",{attrs:{prop:"task_type",label:t.$t("publicLogComponent.renwu-leixing-no"),"header-align":"center",align:"left",width:"180px"}}),i("el-table-column",{attrs:{prop:"task_name",label:t.$t("publicLogComponent.renwu-mingcheng"),"header-align":"center",align:"left","min-width":"100px","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"create_time",label:t.$t("dashboard.chuangjian-shijian"),align:"center",width:"160px","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"last_msg",label:t.$t("dashboard.xin-xi"),align:"center","min-width":"160px"},scopedSlots:t._u([{key:"default",fn:function(e){return[i("el-tooltip",{staticClass:"item",attrs:{effect:"dark",placement:"top"}},[i("div",{staticStyle:{"overflow-y":"auto","white-space":"pre-wrap"},attrs:{slot:"content"},slot:"content"},[i("pre",[t._v(t._s(e.row.last_msg))])]),i("div",{staticStyle:{"white-space":"nowrap",overflow:"hidden","text-overflow":"ellipsis"}},[t._v(t._s(e.row.last_msg))])])]}}],null,!1,3279762957)}),i("el-table-column",{attrs:{prop:"handle",label:t.$t("clusterDefine.caozuo"),align:"center",width:"100px"},scopedSlots:t._u([{key:"default",fn:function(e){return[i("el-button",{staticClass:"normal detail",on:{click:function(i){return t.TaskDetailDialog(e.$index,e.row)}}},[t._v(t._s(t.$t("publicLogComponent.xianshi-xiangqing")))])]}}],null,!1,63140491)})],1):t._e(),i("task-log",{ref:"tasklog"}),i("div",{staticClass:"block",staticStyle:{float:"right"}},[i("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper",total:t.total,"page-sizes":[20,30,40,50,100]},on:{"size-change":t.handleSizeChange,"current-change":t.handleCurrentChange}})],1)],1)],1)}),[],!1,l,"7b4e1c30",null,null);function l(t){for(let e in s)this[e]=s[e]}var n=function(){return a.exports}();export{n as default};
