import{A as t}from"./api_clusterManage.a511e8ac.js";import{s as e}from"./staticTools.84335405.js";import{m as i}from"./dynamicTools.f0febdba.js";import{n}from"./index.ac26e447.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const a={};var s=n({data:()=>({loading:!1,paginationInfo:{currentPage:1,size:10,total:0},filters:{pool_id:""},vipList:[]}),methods:{modifyVipHost(n,a){const{vip:s,host:o}=n;let l={vip:s,host:o,option:a};0===a?i(this.$t("VIPList.qingqueren-shifou-jiechu-m")).then((()=>{this.loading=!0,t.modifyVipOnHost(l).then((t=>{this.getInfo(),this.loading=!1}),(t=>{this.loading=!1}))})).catch((t=>{})):(this.loading=!0,t.modifyVipOnHost(l).then((t=>{e(t),this.getInfo(),this.loading=!1}),(t=>{this.loading=!1})))},search(){this.$refs.pagination.$emit("current-change",1),this.getInfo()},sizeChange(t){this.paginationInfo.size=t,this.getInfo()},currentChange(t){this.paginationInfo.currentPage=t,this.getInfo()},getInfo(){let e={page_size:this.paginationInfo.size,page_num:this.paginationInfo.currentPage,filter:this.filters.pool_id};this.loading=!0,t.getVipList(e).then((t=>{this.paginationInfo.total=t.total,this.vipList=t.rows,this.loading=!1}),(t=>{this.loading=!1}))}},mounted(){this.getInfo()}},(function(){var t=this,e=t.$createElement,i=t._self._c||e;return i("div",[i("el-form",{staticClass:"filterForm",attrs:{model:t.filters},nativeOn:{submit:function(t){t.preventDefault()}}},[i("el-form-item",[i("el-input",{attrs:{placeholder:t.$t("poolList.qingshuru-wangluo-m")},nativeOn:{keyup:function(e){return!e.type.indexOf("key")&&t._k(e.keyCode,"enter",13,e.key,"Enter")?null:t.search(e)}},model:{value:t.filters.pool_id,callback:function(e){t.$set(t.filters,"pool_id",e)},expression:"filters.pool_id"}},[i("el-button",{attrs:{slot:"append",type:"primary"},on:{click:t.search},slot:"append"},[t._v(t._s(t.$t("dbList.shou-suo")))])],1),i("el-tooltip",{attrs:{effect:"dark",content:t.$t("Public.question"),placement:"top"}},[i("i",{staticClass:"el-icon-question"})])],1),i("el-form-item",{staticStyle:{flex:"1","text-align":"right",color:"red"}},[i("el-button",{staticClass:"normal el-icon-refresh-right",on:{click:t.getInfo}},[t._v(" "+t._s(t.$t("resourceManagement.shua-xin")))])],1)],1),i("el-table",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{data:t.vipList,border:"","element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[i("el-table-column",{attrs:{prop:"pool_id",label:t.$t("poolList.vip-chi-id"),align:"center"}}),i("el-table-column",{attrs:{prop:"cluster_name",label:t.$t("clusterDefine.jiqun-mingcheng"),align:"center"}}),i("el-table-column",{attrs:{prop:"cluster_id",label:t.$t("dbList.jiqun-id"),align:"center"}}),i("el-table-column",{attrs:{prop:"db_id",label:t.$t("switchDatabasePage.shujuku-ID"),align:"center"}}),i("el-table-column",{attrs:{prop:"host",label:"HOST",align:"center"}}),i("el-table-column",{attrs:{prop:"vip",label:"VIP",align:"center"}}),i("el-table-column",{attrs:{prop:"used_reason",label:t.$t("dbList.zhuang-tai"),align:"center"},scopedSlots:t._u([{key:"default",fn:function(e){var n=e.row;return[i("span",{class:[{successState:1===n.used_reason},{infoState:2===n.used_reason},{infoState:3===n.used_reason},{warningState:-1===n.used_reason}]},[i("i",{class:[{"el-icon-success":1===n.used_reason},{"el-icon-info":2===n.used_reason},{"el-icon-info":3===n.used_reason},{"el-icon-warning":-1===n.used_reason}]}),t._v(" "+t._s(1===n.used_reason?t.$t("VIPList.yiqiyong"):-1===n.used_reason?t.$t("VIPList.weizhi"):t.$t("VIPList.weiqiyong"))+" ")])]}}])}),i("el-table-column",{attrs:{label:t.$t("dbList.cao-zuo"),align:"center"},scopedSlots:t._u([{key:"default",fn:function(e){var n=e.row;return[2!==n.used_reason&&3!==n.used_reason||!n.host?t._e():i("el-link",{staticClass:"detail",attrs:{size:"mini"},on:{click:function(e){return t.modifyVipHost(n,1)}}},[t._v(t._s(t.$t("VIPList.bangding")))]),1===n.used_reason&&n.host?i("el-link",{staticClass:"detail",attrs:{size:"mini"},on:{click:function(e){return t.modifyVipHost(n,0)}}},[t._v(t._s(t.$t("VIPList.jiebang")))]):t._e()]}}])})],1),i("div",{staticClass:"block clearfix"},[i("div",{staticClass:"fr"},[i("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper","page-size":t.paginationInfo.size,"current-page":t.paginationInfo.currentPage,total:t.paginationInfo.total,"page-sizes":[10,20,30,40,50]},on:{"size-change":t.sizeChange,"current-change":t.currentChange}})],1)])],1)}),[],!1,o,"a17b32a6",null,null);function o(t){for(let e in a)this[e]=a[e]}var l=function(){return s.exports}();export{l as default};
