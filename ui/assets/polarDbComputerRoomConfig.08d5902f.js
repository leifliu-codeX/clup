import{A as e}from"./api_clusterManage.333bcab0.js";import{c as o,d as t}from"./verificationRules.28629627.js";import{n as i}from"./index.c66ec47f.js";const r={};var a=i({name:"dbList",components:{},data(){return{clusterState:this.$route.query.cluster_state,rows:[],total:0,page:1,size:20,roomList:[],loading:!1,addFormVisible:!1,addFormRules:{room_name:[{required:!0,message:this.$t("polarDbComputerRoomConfig.qingshuru-jifangmingcheng"),trigger:"blur"}],vip:[{required:!0,message:this.$t("polarDbComputerRoomConfig.qingshuru-VIP"),trigger:"blur"},{required:!0,validator:o,trigger:"blur"}],read_vip:[{required:!1,message:this.$t("polarDbComputerRoomConfig.qingshuru-zhidu-VIP"),trigger:"blur"},{required:!1,validator:o,trigger:"blur"}],cstlb_list:[{required:!1,validator:t,trigger:"blur"}]},addForm:{scores:100},currentRow:"",editFormVisible:!1,editFormRules:{room_name:[{required:!0,message:this.$t("polarDbComputerRoomConfig.qingshuru-jifangmingcheng"),trigger:"blur"}],vip:[{required:!0,message:this.$t("polarDbComputerRoomConfig.qingshuru-VIP"),trigger:"blur"},{required:!0,validator:o,trigger:"blur"}],read_vip:[{required:!1,message:this.$t("polarDbComputerRoomConfig.qingshuru-zhidu-VIP"),trigger:"blur"},{required:!1,validator:o,trigger:"blur"}],cstlb_list:[{required:!1,validator:t,trigger:"blur"}]},editForm:{}}},watch:{"editForm.is_rewind":function(e){e||(this.editForm.is_rebuild=!1)},"editForm.is_rebuild":function(e){e&&(this.editForm.is_rewind=!0)}},methods:{tableRowClassName:({row:e,rowIndex:o})=>o%2!=0?"warning-row":"success-row",showdbList:function(){let o=this;o.loading=!0;let t={cluster_id:o.$route.query.cluster_id};e.getSrClusterRoomInfo(t).then((function(e){o.loading=!1,o.rows=e}),(function(e){o.loading=!1}))},showAddDialog:function(){this.addForm={room_name:"",vip:"",read_vip:"",cstlb_list:""},this.addFormVisible=!0},addFormSubmit:function(){let e=this;this.$refs.addForm.validate((o=>{if(o){e.addForm;let o=Object.assign({},this.addForm);o.room_id=Number(e.rows[e.rows.length-1].room_id)+1,e.rows.push(o),e.saveRoomChange()}}))},showEditDialog:function(e,o){const t=this;for(var i in t.editFormVisible=!0,t.currentRow=o,t.editForm=Object.assign({},o),t.editForm)t.editForm[i]=t.editForm[i].toString().trim();t.editForm.index=e},saveRoomChange:function(){const o=this;let t={cluster_id:o.$route.query.cluster_id,room_info:{}};o.loading=!0;for(let e=0;e<o.rows.length;e++)t.room_info[o.rows[e].room_id]={room_name:o.rows[e].room_name,vip:o.rows[e].vip,read_vip:o.rows[e].read_vip,cstlb_list:o.rows[e].cstlb_list};e.updateSrClusterRoomInfo(t).then((function(e){o.loading=!1,o.addFormVisible=!1,o.editFormVisible=!1,o.showdbList()}),(function(e){o.loading=!1}))},editFormSubmit:function(){let e=this;e.$refs.editForm.validate((o=>{console.log(o),o&&(e.rows.splice(e.editForm.index,1,e.editForm),e.saveRoomChange())}))},deldbList:function(o,t){this.$confirm(this.$t("polarDbComputerRoomConfig.qingqueren-jiangci-message")+t.room_id+this.$t("polarDbComputerRoomConfig.jifang-mingcheng-message")+t.room_name+this.$t("polarDbComputerRoomConfig.yichuma-mewssage"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{const o=this;let i={cluster_id:o.$route.query.cluster_id,room_id:t.room_id};o.loading=!0,e.deleteSrClusterRoomInfo(i).then((function(e){o.loading=!1,o.showdbList()}),(function(e){o.loading=!1}))})).catch((()=>{}))}},mounted:function(){this.showdbList()},destroyed(){clearInterval(this.intervalID)}},(function(){var e=this,o=e.$createElement,t=e._self._c||o;return t("el-row",[t("el-col",[0===e.clusterState||-1===e.clusterState?t("el-button",{staticStyle:{margin:"10px 0"},attrs:{type:"primary"},on:{click:e.showAddDialog}},[e._v(e._s(e.$t("polarDbComputerRoomConfig.zeng-jia")))]):e._e(),t("el-table",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{"row-class-name":e.tableRowClassName,data:e.rows,border:"","element-loading-text":e.$t("Public.ping-ming-jia-zai-zhong")}},[t("el-table-column",{attrs:{prop:"room_id",label:e.$t("polarDbComputerRoomConfig.jifang-id"),align:"center",width:"120px"}}),t("el-table-column",{attrs:{prop:"room_name",label:e.$t("dbList.jifang-mingcheng"),align:"center",width:"120px"},scopedSlots:e._u([{key:"default",fn:function(o){return[t("span",{staticClass:"statefont"},[e._v(" "+e._s("默认机房"==o.row.room_name?e.$t("dbList.moren-jifang"):o.row.room_name))])]}}])}),t("el-table-column",{attrs:{prop:"vip",label:"vip",align:"center",width:"150px"}}),t("el-table-column",{attrs:{prop:"read_vip",label:e.$t("polarDbComputerRoomConfig.zhidu-vip"),align:"center",width:"150px"}}),t("el-table-column",{attrs:{prop:"room_use_state",label:e.$t("polarDbComputerRoomConfig.shiyong-zhuangtai"),align:"center",width:"150px"},scopedSlots:e._u([{key:"default",fn:function(o){return[1==o.row.room_use_state?t("i",{staticClass:"el-icon-success green"},[t("span",[e._v(" "+e._s(e.$t("polarDbComputerRoomConfig.yi-shi-yong")))])]):e._e(),0==o.row.room_use_state?t("i",{staticClass:"el-icon-info"},[t("span",[e._v(" "+e._s(e.$t("polarDbComputerRoomConfig.wei-shi-yong")))])]):e._e()]}}])}),t("el-table-column",{attrs:{prop:"cstlb_list",label:e.$t("createStreamReplicationCluster.junhenqi-liebiao"),align:"center"}}),t("el-table-column",{attrs:{prop:"handle",label:e.$t("clusterDefine.caozuo"),align:"center",width:"150px"},scopedSlots:e._u([{key:"default",fn:function(o){return[0==e.clusterState||-1==e.clusterState?t("span",[t("el-link",{staticClass:"normal",on:{click:function(t){return e.showEditDialog(o.$index,o.row)}}},[e._v(e._s(e.$t("alarmSet.xiugai")))]),1!==o.row.is_primary?t("el-link",{staticClass:"normal",on:{click:function(t){return e.deldbList(o.$index,o.row)}}},[e._v(e._s(e.$t("alarmInformationConfig.yichu")))]):e._e()],1):e._e()]}}])})],1),t("el-dialog",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],attrs:{"append-to-body":!0,title:e.$t("polarDbComputerRoomConfig.tianjia-shujuku-shili"),visible:e.addFormVisible,"close-on-click-modal":!1,"element-loading-text":e.$t("Public.ping-ming-jia-zai-zhong")},on:{"update:visible":function(o){e.addFormVisible=o}}},[t("el-form",{ref:"addForm",staticStyle:{width:"90%"},attrs:{model:e.addForm,"label-width":"100px",rules:e.addFormRules}},[t("el-form-item",{attrs:{label:e.$t("dbList.jifang-mingcheng"),prop:"room_name"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-jifangmingcheng")},model:{value:e.addForm.room_name,callback:function(o){e.$set(e.addForm,"room_name",o)},expression:"addForm.room_name"}})],1),t("el-form-item",{attrs:{label:"vip",prop:"vip"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-vip")},model:{value:e.addForm.vip,callback:function(o){e.$set(e.addForm,"vip",o)},expression:"addForm.vip"}})],1),t("el-form-item",{attrs:{label:e.$t("polarDbComputerRoomConfig.zhidu-vip"),prop:"read_vip"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-read_vip")},model:{value:e.addForm.read_vip,callback:function(o){e.$set(e.addForm,"read_vip",o)},expression:"addForm.read_vip"}})],1),t("el-form-item",{attrs:{label:e.$t("createStreamReplicationCluster.junhenqi-liebiao"),prop:"cstlb_list"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-jujnhengqi-liebiao")},model:{value:e.addForm.cstlb_list,callback:function(o){e.$set(e.addForm,"cstlb_list",o)},expression:"addForm.cstlb_list"}})],1)],1),t("div",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{nativeOn:{click:function(o){e.addFormVisible=!1}}},[e._v(e._s(e.$t("index.qu-xiao")))]),t("el-button",{attrs:{type:"primary",loading:e.loading},nativeOn:{click:function(o){return e.addFormSubmit(o)}}},[e._v(e._s(e.$t("defineDatabasePage.ti-jiao")))])],1)],1),t("el-dialog",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],attrs:{"append-to-body":!0,title:e.$t("alarmSet.xiugai"),visible:e.editFormVisible,"close-on-click-modal":!1,"element-loading-text":e.$t("Public.ping-ming-jia-zai-zhong")},on:{"update:visible":function(o){e.editFormVisible=o}}},[t("el-form",{ref:"editForm",staticStyle:{width:"90%"},attrs:{model:e.editForm,"label-width":"140px",rules:e.editFormRules}},[t("el-form-item",{attrs:{label:e.$t("dbList.jifang-mingcheng"),prop:"room_name"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-jifangmingcheng")},model:{value:e.editForm.room_name,callback:function(o){e.$set(e.editForm,"room_name",o)},expression:"editForm.room_name"}})],1),t("el-form-item",{attrs:{label:"vip",prop:"vip"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-vip")},model:{value:e.editForm.vip,callback:function(o){e.$set(e.editForm,"vip",o)},expression:"editForm.vip"}})],1),t("el-form-item",{attrs:{label:e.$t("polarDbComputerRoomConfig.zhidu-vip"),prop:"read_vip"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-read_vip")},model:{value:e.editForm.read_vip,callback:function(o){e.$set(e.editForm,"read_vip",o)},expression:"editForm.read_vip"}})],1),t("el-form-item",{attrs:{label:e.$t("createStreamReplicationCluster.junhenqi-liebiao"),prop:"cstlb_list"}},[t("el-input",{attrs:{placeholder:e.$t("polarDbComputerRoomConfig.qingshuru-jujnhengqi-liebiao")},model:{value:e.editForm.cstlb_list,callback:function(o){e.$set(e.editForm,"cstlb_list",o)},expression:"editForm.cstlb_list"}})],1)],1),t("div",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{nativeOn:{click:function(o){e.editFormVisible=!1}}},[e._v(e._s(e.$t("index.qu-xiao")))]),t("el-button",{attrs:{type:"primary",loading:e.loading},nativeOn:{click:function(o){return e.editFormSubmit(o)}}},[e._v(e._s(e.$t("defineDatabasePage.ti-jiao")))])],1)],1)],1)],1)}),[],!1,l,"02ee1341",null,null);function l(e){for(let o in r)this[o]=r[o]}var n=function(){return a.exports}();export{n as p};
