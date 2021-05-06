<template>
  <div id="app">
    <template v-if="loading">
      <loading-spinner></loading-spinner>
    </template>

    <div v-if="!loading">
      <div class="row">
        <div class="col-12" style="text-align: center">
          <h3>{{ recipe.name }}</h3>
        </div>
      </div>

      <div class="my-auto">
        <div class="col-12" style="text-align: center">
          <i>{{ recipe.description }}</i>
        </div>
      </div>

      <div style="text-align: center">
        <keywords :recipe="recipe"></keywords>
      </div>

      <hr/>
      <div class="row">
        <div class="col col-md-3">
          <div class="row d-flex" style="padding-left: 16px">
            <div class="my-auto" style="padding-right: 4px">
              <i class="fas fa-user-clock fa-2x text-primary"></i>
            </div>
            <div class="my-auto" style="padding-right: 4px">
              <span class="text-primary"><b>{{ $t('Preparation') }}</b></span><br/>
              {{ recipe.working_time }} {{ $t('min') }}
            </div>
          </div>
        </div>

        <div class="col col-md-3">
          <div class="row d-flex">
            <div class="my-auto" style="padding-right: 4px">
              <i class="far fa-clock fa-2x text-primary"></i>
            </div>
            <div class="my-auto" style="padding-right: 4px">
              <span class="text-primary"><b>{{ $t('Waiting') }}</b></span><br/>
              {{ recipe.waiting_time }} {{ $t('min') }}
            </div>
          </div>
        </div>

        <div class="col col-md-4 col-10">
          <div class="row d-flex" style="padding-left: 16px">
            <div class="my-auto" style="padding-right: 4px">
              <i class="fas fa-pizza-slice fa-2x text-primary"></i>
            </div>
            <div class="my-auto" style="padding-right: 4px">
              <input style="text-align: right; border-width:0px;border:none; padding:0px; padding-left: 0.5vw; padding-right: 8px; max-width: 80px"
                     value="1" maxlength="3" min="0"
                     type="number" class="form-control form-control-lg" v-model.number="servings"/>
            </div>
            <div class="my-auto">
              <b><template v-if="recipe.servings_text === ''">{{ $t('Servings') }}</template><template v-else>{{recipe.servings_text}}</template></b>
            </div>
          </div>
        </div>

        <div class="col col-md-2 col-2 my-auto" style="text-align: right; padding-right: 1vw">
          <recipe-context-menu v-bind:recipe="recipe" :servings="servings"></recipe-context-menu>
        </div>
      </div>
      <hr/>

      <div class="row">
        <div class="col-md-6 order-md-1 col-sm-12 order-sm-2 col-12 order-2" v-if="recipe && ingredient_count > 0">
          <div class="card border-primary">
            <div class="card-body">
              <div class="row">
                <div class="col col-md-8">
                  <h4 class="card-title"><i class="fas fa-pepper-hot"></i> {{ $t('Ingredients') }}</h4>
                </div>
              </div>
              <br/>
              <div class="row">
                <div class="col-md-12">
                  <table class="table table-sm">
                    <!-- eslint-disable vue/no-v-for-template-key-on-child -->
                    <template v-for="s in recipe.steps">
                      <template v-for="i in s.ingredients">
                        <Ingredient :ingredient="i" :ingredient_factor="ingredient_factor" :key="i.id"
                                    @checked-state-changed="updateIngredientCheckedState"></Ingredient>
                      </template>
                    </template>
                    <!-- eslint-enable vue/no-v-for-template-key-on-child -->
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="col-12 order-1 col-sm-12 order-sm-1 col-md-6 order-md-2">
          <div class="row">
            <div class="col-12">

              <img class="img img-fluid rounded" :src="recipe.image" style="max-height: 30vh;"
                   :alt="$t( 'Recipe_Image')" v-if="recipe.image !== null">
            </div>
          </div>

          <div class="row" style="margin-top: 2vh; margin-bottom: 2vh">
            <div class="col-12">
              <Nutrition :recipe="recipe" :ingredient_factor="ingredient_factor"></Nutrition>
            </div>
          </div>
        </div>


      </div>

      <template v-if="!recipe.internal">
        <div v-if="recipe.file_path.includes('.pdf')">
          <PdfViewer :recipe="recipe"></PdfViewer>
        </div>
        <div
            v-if="recipe.file_path.includes('.png') || recipe.file_path.includes('.jpg') || recipe.file_path.includes('.jpeg') || recipe.file_path.includes('.gif')">
          <ImageViewer :recipe="recipe"></ImageViewer>
        </div>
      </template>


      <div v-for="(s, index) in recipe.steps" v-bind:key="s.id" style="margin-top: 1vh">
        <Step :recipe="recipe" :step="s" :ingredient_factor="ingredient_factor" :index="index" :start_time="start_time"
              @update-start-time="updateStartTime" @checked-state-changed="updateIngredientCheckedState"></Step>
      </div>
    </div>

    <add-recipe-to-book :recipe="recipe"></add-recipe-to-book>
  </div>
</template>

<script>
import Vue from 'vue'
import {BootstrapVue} from 'bootstrap-vue'

import 'bootstrap-vue/dist/bootstrap-vue.css'

import {apiLoadRecipe} from "@/utils/api";

import Step from "@/components/Step";
import RecipeContextMenu from "@/components/RecipeContextMenu";
import {ResolveUrlMixin, ToastMixin} from "@/utils/utils";
import Ingredient from "@/components/Ingredient";

import PdfViewer from "@/components/PdfViewer";
import ImageViewer from "@/components/ImageViewer";
import Nutrition from "@/components/Nutrition";

import moment from 'moment'
import Keywords from "@/components/Keywords";
import LoadingSpinner from "@/components/LoadingSpinner";
import AddRecipeToBook from "@/components/AddRecipeToBook";

Vue.prototype.moment = moment

Vue.use(BootstrapVue)

export default {
  name: 'RecipeView',
  mixins: [
    ResolveUrlMixin,
    ToastMixin,
  ],
  components: {
    PdfViewer,
    ImageViewer,
    Ingredient,
    Step,
    RecipeContextMenu,
    Nutrition,
    Keywords,
    LoadingSpinner,
    AddRecipeToBook,
  },
  computed: {
    ingredient_factor: function () {
      return this.servings / this.recipe.servings
    },
  },
  data() {
    return {
      loading: true,
      recipe: undefined,
      ingredient_count: 0,
      servings: 1,
      start_time: ""
    }
  },
  mounted() {
    this.loadRecipe(window.RECIPE_ID)
  },
  methods: {
    loadRecipe: function (recipe_id) {
      apiLoadRecipe(recipe_id).then(recipe => {

        if (window.USER_SERVINGS !== 0) {
          recipe.servings = window.USER_SERVINGS
        }
        this.servings = recipe.servings

        let total_time = 0
        for (let step of recipe.steps) {
          this.ingredient_count += step.ingredients.length

          for (let ingredient of step.ingredients) {
            this.$set(ingredient, 'checked', false)
          }

          step.time_offset = total_time
          total_time += step.time
        }

        // set start time only if there are any steps with timers (otherwise no timers are rendered)
        if (total_time > 0) {
          this.start_time = moment().format('yyyy-MM-DDTHH:mm')
        }

        this.recipe = recipe
        this.loading = false
      })
    },
    updateStartTime: function (e) {
      this.start_time = e
    },
    updateIngredientCheckedState: function (e) {
      for (let step of this.recipe.steps) {
        for (let ingredient of step.ingredients) {
          if (ingredient.id === e.id) {
            this.$set(ingredient, 'checked', !ingredient.checked)
          }
        }
      }
    },
  }
}

</script>

<style>


</style>
